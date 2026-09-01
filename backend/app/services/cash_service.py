from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import CashOperation, Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.schemas.cash import CashBalanceRead, CashBookRow, CashOperationCreate, CashOperationInternalCreate
from app.services.audit_writer import change_details, write_audit


CASH_LOCK_KEY = 0x43415348


def _lock_cash(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(CASH_LOCK_KEY)))


def _direction_for_type(operation_type: str) -> str:
    if operation_type == CashOperation.TYPE_CASH_IN:
        return "in"
    if operation_type == CashOperation.TYPE_CASH_OUT:
        return "out"
    raise HTTPException(status_code=422, detail="Invalid cash operation type")


def _balance_effect(operation: CashOperation) -> Decimal:
    if operation.status == CashOperation.STATUS_CANCELLED:
        return Decimal("0")
    if operation.operation_type == CashOperation.TYPE_CASH_IN:
        return operation.amount
    if operation.operation_type == CashOperation.TYPE_CASH_OUT:
        return -operation.amount
    if operation.operation_type == CashOperation.TYPE_CORRECTION:
        if operation.direction == "in":
            return operation.amount
        if operation.direction == "out":
            return -operation.amount
        # Compatibility for correction rows created before target-balance semantics.
        return operation.amount
    return Decimal("0")


def _assert_nonnegative_ledger(
    db: Session,
    *,
    excluded_operation_ids: set[int] | None = None,
    pending_operation: CashOperation | None = None,
) -> None:
    excluded = excluded_operation_ids or set()
    operations = [
        operation
        for operation in db.scalars(select(CashOperation)).all()
        if operation.id not in excluded and operation.status == CashOperation.STATUS_POSTED
    ]
    if pending_operation is not None:
        operations.append(pending_operation)
    operations.sort(key=lambda operation: (operation.operation_date, operation.id or 2**63 - 1))
    balance = Decimal("0")
    for operation in operations:
        balance += _balance_effect(operation)
        if balance < 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cash balance cannot be negative on {operation.operation_date.isoformat()}",
            )


def _load_operation(db: Session, operation_id: int) -> CashOperation:
    operation = db.scalar(
        select(CashOperation)
        .where(CashOperation.id == operation_id)
        .options(selectinload(CashOperation.partner), selectinload(CashOperation.payment))
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Cash operation not found")
    return operation


def create_cash_operation(
    db: Session,
    payload: CashOperationCreate | CashOperationInternalCreate,
    *,
    commit: bool = True,
) -> CashOperation:
    _lock_cash(db)
    if payload.partner_id is not None and db.get(Partner, payload.partner_id) is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    if payload.document_id is not None and db.get(Document, payload.document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    payment_id = getattr(payload, "payment_id", None)
    if payment_id is not None and db.get(Payment, payment_id) is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    target_balance: Decimal | None = None
    amount = payload.amount
    if payload.operation_type == CashOperation.TYPE_CORRECTION:
        if not payload.note or not payload.note.strip():
            raise HTTPException(status_code=422, detail="Cash correction requires a reason")
        target_balance = payload.amount
        difference = target_balance - get_cash_balance(db).balance
        amount = abs(difference)
        direction = "in" if difference > 0 else "out" if difference < 0 else "correction"
    else:
        if payload.amount <= 0:
            raise HTTPException(status_code=422, detail="Cash operation amount must be greater than zero")
        direction = _direction_for_type(payload.operation_type)

    operation = CashOperation(
        operation_date=payload.operation_date,
        operation_type=payload.operation_type,
        direction=direction,
        status=CashOperation.STATUS_POSTED,
        amount=amount,
        target_balance=target_balance,
        partner_id=payload.partner_id,
        document_id=payload.document_id,
        payment_id=payment_id,
        created_by_id=db.info.get("actor_user_id"),
        note=payload.note,
    )
    _assert_nonnegative_ledger(db, pending_operation=operation)
    db.add(operation)
    db.flush()
    write_audit(
        db,
        "cash_operation",
        operation.id,
        "create",
        change_details(
            {},
            {
                "operation_type": operation.operation_type,
                "direction": operation.direction,
                "amount": operation.amount,
                "target_balance": operation.target_balance,
            },
        ),
    )
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def cancel_cash_operation(db: Session, operation_id: int, *, commit: bool = True) -> CashOperation:
    _lock_cash(db)
    operation = _load_operation(db, operation_id)
    if operation.status != CashOperation.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted cash operations can be cancelled")
    _assert_nonnegative_ledger(db, excluded_operation_ids={operation.id})
    operation.status = CashOperation.STATUS_CANCELLED
    write_audit(
        db,
        "cash_operation",
        operation.id,
        "cancel",
        change_details({"status": CashOperation.STATUS_POSTED}, {"status": CashOperation.STATUS_CANCELLED}),
    )
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def cancel_payment_cash_operations(db: Session, payment_id: int) -> list[CashOperation]:
    _lock_cash(db)
    operations = list(db.scalars(select(CashOperation).where(CashOperation.payment_id == payment_id)))
    posted_ids = {operation.id for operation in operations if operation.status == CashOperation.STATUS_POSTED}
    _assert_nonnegative_ledger(db, excluded_operation_ids=posted_ids)
    for operation in operations:
        if operation.status == CashOperation.STATUS_POSTED:
            operation.status = CashOperation.STATUS_CANCELLED
            write_audit(
                db,
                "cash_operation",
                operation.id,
                "cancel",
                change_details(
                    {"status": CashOperation.STATUS_POSTED},
                    {"status": CashOperation.STATUS_CANCELLED},
                ),
            )
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
                target_balance=operation.target_balance,
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
