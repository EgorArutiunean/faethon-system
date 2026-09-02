from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.documents import Document
from app.models.identity import User
from app.models.logistics import WarehouseTask, WarehouseTaskEvent, WarehouseTaskLine
from app.schemas.logistics import (
    WarehouseTaskConfirmation,
    WarehouseTaskEventRead,
    WarehouseTaskLineRead,
    WarehouseTaskRead,
)
from app.services.audit_writer import write_audit


ACTIVE_TASK_STATUSES = {
    WarehouseTask.STATUS_BLOCKED,
    WarehouseTask.STATUS_PENDING,
    WarehouseTask.STATUS_IN_TRANSIT,
    WarehouseTask.STATUS_IN_PROGRESS,
    WarehouseTask.STATUS_NEEDS_REVIEW,
}
TASK_STATUSES = ACTIVE_TASK_STATUSES | {
    WarehouseTask.STATUS_COMPLETED,
    WarehouseTask.STATUS_CANCELLED,
}


def _task_options():
    return (
        selectinload(WarehouseTask.document).selectinload(Document.partner),
        selectinload(WarehouseTask.warehouse),
        selectinload(WarehouseTask.assigned_to),
        selectinload(WarehouseTask.lines).selectinload(WarehouseTaskLine.product),
        selectinload(WarehouseTask.events).selectinload(WarehouseTaskEvent.actor),
    )


def _task_query():
    return select(WarehouseTask).options(*_task_options())


def _can_review(user: User) -> bool:
    return "logistics.review" in user.permissions


def _ensure_task_access(task: WarehouseTask, user: User) -> None:
    if not _can_review(user) and task.warehouse_id not in user.warehouse_ids:
        raise HTTPException(status_code=404, detail="Warehouse task not found")


def _load_task(db: Session, task_id: int, user: User) -> WarehouseTask:
    task = db.scalar(_task_query().where(WarehouseTask.id == task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Warehouse task not found")
    _ensure_task_access(task, user)
    return task


def _lock_task(db: Session, task_id: int, user: User) -> WarehouseTask:
    task = db.scalar(select(WarehouseTask).where(WarehouseTask.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status_code=404, detail="Warehouse task not found")
    _ensure_task_access(task, user)
    return task


def _event(
    db: Session,
    task: WarehouseTask,
    event_type: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
) -> None:
    db.add(
        WarehouseTaskEvent(
            task_id=task.id,
            actor_user_id=db.info.get("actor_user_id"),
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )


def _task_specs(document: Document) -> list[tuple[int, str, str]]:
    if document.document_type == Document.TYPE_INCOMING and document.warehouse_id is not None:
        return [(document.warehouse_id, WarehouseTask.TYPE_INCOMING_RECEIVE, WarehouseTask.STATUS_PENDING)]
    if document.document_type == Document.TYPE_OUTGOING and document.warehouse_id is not None:
        return [(document.warehouse_id, WarehouseTask.TYPE_OUTGOING_DISPATCH, WarehouseTask.STATUS_PENDING)]
    if (
        document.document_type == Document.TYPE_TRANSFER
        and document.warehouse_id is not None
        and document.destination_warehouse_id is not None
    ):
        return [
            (document.warehouse_id, WarehouseTask.TYPE_TRANSFER_DISPATCH, WarehouseTask.STATUS_PENDING),
            (document.destination_warehouse_id, WarehouseTask.TYPE_TRANSFER_RECEIVE, WarehouseTask.STATUS_BLOCKED),
        ]
    return []


def create_tasks_for_document(db: Session, document: Document) -> None:
    if document.status != Document.STATUS_POSTED or document.posting_version <= 0:
        return
    db.flush()
    for warehouse_id, task_type, status in _task_specs(document):
        existing_id = db.scalar(
            select(WarehouseTask.id).where(
                WarehouseTask.document_id == document.id,
                WarehouseTask.posting_version == document.posting_version,
                WarehouseTask.warehouse_id == warehouse_id,
                WarehouseTask.task_type == task_type,
            )
        )
        if existing_id is not None:
            continue
        task = WarehouseTask(
            document_id=document.id,
            posting_version=document.posting_version,
            warehouse_id=warehouse_id,
            task_type=task_type,
            status=status,
        )
        db.add(task)
        db.flush()
        for document_line in document.lines:
            sale_price = (
                document_line.price
                if document.document_type == Document.TYPE_OUTGOING
                else document_line.product.base_price or Decimal("0")
            )
            db.add(
                WarehouseTaskLine(
                    task_id=task.id,
                    document_line_id=document_line.id,
                    product_id=document_line.product_id,
                    expected_quantity=document_line.quantity,
                    sale_price=sale_price,
                    status=WarehouseTaskLine.STATUS_PENDING,
                )
            )
        _event(db, task, "generated", to_status=status)


def cancel_active_tasks_for_document_version(
    db: Session,
    document_id: int,
    posting_version: int,
    reason: str,
) -> None:
    tasks = db.scalars(
        select(WarehouseTask)
        .where(
            WarehouseTask.document_id == document_id,
            WarehouseTask.posting_version == posting_version,
            WarehouseTask.status.in_(ACTIVE_TASK_STATUSES),
        )
        .with_for_update()
    ).all()
    now = datetime.now(timezone.utc)
    for task in tasks:
        previous = task.status
        task.status = WarehouseTask.STATUS_CANCELLED
        task.completed_at = now
        _event(db, task, "cancelled", from_status=previous, to_status=task.status, note=reason)


def list_tasks(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[WarehouseTask]:
    if status is not None and status not in TASK_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid warehouse task status")
    statement = _task_query()
    if not _can_review(user):
        if not user.warehouse_ids:
            return []
        statement = statement.where(WarehouseTask.warehouse_id.in_(user.warehouse_ids))
    if status is not None:
        statement = statement.where(WarehouseTask.status == status)
    statement = statement.order_by(WarehouseTask.created_at.desc(), WarehouseTask.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


def get_task(db: Session, task_id: int, user: User) -> WarehouseTask:
    return _load_task(db, task_id, user)


def start_task(db: Session, task_id: int, user: User) -> WarehouseTask:
    task = _lock_task(db, task_id, user)
    if task.status not in {WarehouseTask.STATUS_PENDING, WarehouseTask.STATUS_IN_TRANSIT}:
        raise HTTPException(status_code=409, detail="Only pending warehouse task can be started")
    previous = task.status
    task.status = WarehouseTask.STATUS_IN_PROGRESS
    task.assigned_to_id = user.id
    task.started_at = datetime.now(timezone.utc)
    task.completed_at = None
    _event(db, task, "started", from_status=previous, to_status=task.status)
    write_audit(db, "warehouse_task", task.id, "started")
    db.commit()
    return _load_task(db, task.id, user)


def _validate_confirmation(task: WarehouseTask, payload: WarehouseTaskConfirmation) -> dict[int, tuple[Decimal, str | None]]:
    submitted_ids = [line.line_id for line in payload.lines]
    expected_ids = {line.id for line in task.lines}
    if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != expected_ids:
        raise HTTPException(status_code=422, detail="Every warehouse task line must be confirmed exactly once")
    values: dict[int, tuple[Decimal, str | None]] = {}
    task_lines = {line.id: line for line in task.lines}
    for item in payload.lines:
        task_line = task_lines[item.line_id]
        comment = item.comment.strip() if item.comment else None
        if item.actual_quantity != task_line.expected_quantity and not comment:
            raise HTTPException(status_code=422, detail="Discrepancy comment is required")
        values[item.line_id] = (item.actual_quantity, comment)
    return values


def _activate_transfer_receive(db: Session, task: WarehouseTask) -> None:
    if task.task_type != WarehouseTask.TYPE_TRANSFER_DISPATCH:
        return
    receive_task = db.scalar(
        select(WarehouseTask)
        .where(
            WarehouseTask.document_id == task.document_id,
            WarehouseTask.posting_version == task.posting_version,
            WarehouseTask.task_type == WarehouseTask.TYPE_TRANSFER_RECEIVE,
            WarehouseTask.status == WarehouseTask.STATUS_BLOCKED,
        )
        .with_for_update()
    )
    if receive_task is None:
        return
    receive_task.status = WarehouseTask.STATUS_IN_TRANSIT
    _event(
        db,
        receive_task,
        "unblocked",
        from_status=WarehouseTask.STATUS_BLOCKED,
        to_status=WarehouseTask.STATUS_IN_TRANSIT,
        note="Отправка перемещения завершена",
    )


def confirm_task(
    db: Session,
    task_id: int,
    payload: WarehouseTaskConfirmation,
    user: User,
) -> WarehouseTask:
    locked_task = _lock_task(db, task_id, user)
    task = db.scalar(_task_query().where(WarehouseTask.id == locked_task.id))
    assert task is not None
    if task.status != WarehouseTask.STATUS_IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Only active warehouse task can be confirmed")
    if task.assigned_to_id != user.id and not _can_review(user):
        raise HTTPException(status_code=409, detail="Warehouse task is assigned to another user")
    values = _validate_confirmation(task, payload)
    has_discrepancy = False
    for task_line in task.lines:
        actual_quantity, comment = values[task_line.id]
        task_line.actual_quantity = actual_quantity
        task_line.comment = comment
        if actual_quantity == task_line.expected_quantity:
            task_line.status = WarehouseTaskLine.STATUS_CONFIRMED
        else:
            task_line.status = WarehouseTaskLine.STATUS_DISCREPANCY
            has_discrepancy = True
    previous = task.status
    task.status = WarehouseTask.STATUS_NEEDS_REVIEW if has_discrepancy else WarehouseTask.STATUS_COMPLETED
    task.completed_at = datetime.now(timezone.utc) if not has_discrepancy else None
    event_type = "discrepancy_reported" if has_discrepancy else "completed"
    _event(db, task, event_type, from_status=previous, to_status=task.status)
    if not has_discrepancy:
        _activate_transfer_receive(db, task)
    write_audit(db, "warehouse_task", task.id, event_type)
    db.commit()
    return _load_task(db, task.id, user)


def return_task(db: Session, task_id: int, note: str, user: User) -> WarehouseTask:
    task = _lock_task(db, task_id, user)
    if not _can_review(user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if task.status != WarehouseTask.STATUS_NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail="Only task with discrepancies can be returned")
    previous = task.status
    task.status = WarehouseTask.STATUS_PENDING
    task.assigned_to_id = None
    task.started_at = None
    task.completed_at = None
    for line in task.lines:
        line.status = WarehouseTaskLine.STATUS_PENDING
    _event(db, task, "returned", from_status=previous, to_status=task.status, note=note.strip())
    write_audit(db, "warehouse_task", task.id, "returned", note.strip())
    db.commit()
    return _load_task(db, task.id, user)


def serialize_task(task: WarehouseTask) -> WarehouseTaskRead:
    return WarehouseTaskRead(
        id=task.id,
        document_id=task.document_id,
        document_number=task.document_number,
        document_date=task.document_date,
        document_type=task.document_type,
        posting_version=task.posting_version,
        partner_name=task.partner_name,
        warehouse_id=task.warehouse_id,
        warehouse_name=task.warehouse_name,
        task_type=task.task_type,
        status=task.status,
        assigned_to_id=task.assigned_to_id,
        assigned_to_name=task.assigned_to_name,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        lines=[
            WarehouseTaskLineRead(
                id=line.id,
                product_id=line.product_id,
                product_name=line.product_name,
                expected_quantity=line.expected_quantity,
                actual_quantity=line.actual_quantity,
                status=line.status,
                comment=line.comment,
                sale_price=line.sale_price,
                sale_total=(line.expected_quantity * line.sale_price).quantize(Decimal("0.01")),
            )
            for line in task.lines
        ],
        events=[
            WarehouseTaskEventRead(
                id=event.id,
                event_type=event.event_type,
                actor_user_id=event.actor_user_id,
                actor_name=event.actor_name,
                from_status=event.from_status,
                to_status=event.to_status,
                note=event.note,
                created_at=event.created_at,
            )
            for event in task.events
        ],
    )
