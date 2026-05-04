from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import AuditLog, CashOperation
from app.models.partners import Partner
from app.schemas.cash import CashBalanceRead, CashBookRow, CashOperationCreate


def _audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, details=details))


def _direction_for_type(operation_type: str) -> str:
    if operation_type == CashOperation.TYPE_CASH_IN:
        return "in"
    if operation_type == CashOperation.TYPE_CASH_OUT:
        return "out"
    if operation_type == CashOperation.TYPE_CORRECTION:
        return "correction"
    raise HTTPException(status_code=422, detail="Invalid cash operation type")


def _balance_effect(operation: CashOperation) -> Decimal:
    if operation.status == CashOperation.STATUS_CANCELLED:
        return Decimal("0")
    if operation.operation_type == CashOperation.TYPE_CASH_IN:
        return operation.amount
    if operation.operation_type == CashOperation.TYPE_CASH_OUT:
        return -operation.amount
    if operation.operation_type == CashOperation.TYPE_CORRECTION:
        # TODO LEGACY_RULE_REQUIRED: confirm whether cash correction is an absolute balance or signed delta.
        return operation.amount
    return Decimal("0")


def _load_operation(db: Session, operation_id: int) -> CashOperation:
    operation = db.scalar(
        select(CashOperation)
        .where(CashOperation.id == operation_id)
        .options(selectinload(CashOperation.partner), selectinload(CashOperation.payment))
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Cash operation not found")
    return operation


def create_cash_operation(db: Session, payload: CashOperationCreate, *, commit: bool = True) -> CashOperation:
    if payload.partner_id is not None and db.get(Partner, payload.partner_id) is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    operation = CashOperation(
        operation_date=payload.operation_date,
        operation_type=payload.operation_type,
        direction=_direction_for_type(payload.operation_type),
        status=CashOperation.STATUS_POSTED,
        amount=payload.amount,
        partner_id=payload.partner_id,
        document_id=payload.document_id,
        payment_id=payload.payment_id,
        created_by_id=payload.created_by_id,
        note=payload.note,
    )
    db.add(operation)
    db.flush()
    _audit(db, "cash_operation", operation.id, "create", f"type={operation.operation_type}")
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def cancel_cash_operation(db: Session, operation_id: int, *, commit: bool = True) -> CashOperation:
    operation = _load_operation(db, operation_id)
    if operation.status != CashOperation.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted cash operations can be cancelled")
    operation.status = CashOperation.STATUS_CANCELLED
    _audit(db, "cash_operation", operation.id, "cancel")
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def cancel_payment_cash_operations(db: Session, payment_id: int) -> list[CashOperation]:
    operations = list(db.scalars(select(CashOperation).where(CashOperation.payment_id == payment_id)))
    for operation in operations:
        if operation.status == CashOperation.STATUS_POSTED:
            operation.status = CashOperation.STATUS_CANCELLED
            _audit(db, "cash_operation", operation.id, "cancel", f"payment_id={payment_id}")
    return operations


def list_cash_operations(db: Session, skip: int = 0, limit: int = 100) -> list[CashOperation]:
    stmt = (
        select(CashOperation)
        .options(selectinload(CashOperation.partner), selectinload(CashOperation.payment))
        .order_by(CashOperation.operation_date, CashOperation.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_cash_balance(db: Session) -> CashBalanceRead:
    balance = Decimal("0")
    for operation in db.scalars(select(CashOperation)):
        balance += _balance_effect(operation)
    return CashBalanceRead(balance=balance)


def get_cash_book(db: Session) -> list[CashBookRow]:
    balance = Decimal("0")
    rows: list[CashBookRow] = []
    for operation in list_cash_operations(db, limit=1000):
        balance += _balance_effect(operation)
        rows.append(
            CashBookRow(
                id=operation.id,
                operation_date=operation.operation_date,
                operation_type=operation.operation_type,
                direction=operation.direction,
                status=operation.status,
                amount=operation.amount,
                partner_id=operation.partner_id,
                document_id=operation.document_id,
                payment_id=operation.payment_id,
                created_by_id=operation.created_by_id,
                note=operation.note,
                partner_name=operation.partner_name,
                payment_status=operation.payment_status,
                created_at=operation.created_at,
                updated_at=operation.updated_at,
                balance=balance,
            )
        )
    return rows
