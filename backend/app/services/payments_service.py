from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import CashOperation, Payment, PaymentAllocation
from app.models.documents import Document
from app.models.partners import Partner
from app.schemas.cash import CashOperationInternalCreate
from app.schemas.payments import (
    PaymentAllocationInput,
    PaymentAllocationOption,
    PaymentCreate,
    PaymentUpdate,
    PartnerBalanceRead,
    PartnerStatementRow,
)
from app.services import cash_service
from app.services.audit_writer import change_details, write_audit


def _load_payment(db: Session, payment_id: int, *, for_update: bool = False) -> Payment:
    statement = (
        select(Payment)
        .where(Payment.id == payment_id)
        .options(
            selectinload(Payment.partner),
            selectinload(Payment.document),
            selectinload(Payment.cash_operations),
            selectinload(Payment.allocations).selectinload(PaymentAllocation.document),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    payment = db.scalar(statement)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


def _document_balance_effect(document: Document) -> Decimal:
    # Positive balance means partner owes us. Negative balance means we owe partner.
    # TODO LEGACY_RULE_REQUIRED: confirm debt signs and document types against legacy accounting.
    if document.status != Document.STATUS_POSTED:
        return Decimal("0")
    if document.document_type == Document.TYPE_OUTGOING:
        return document.total_amount
    if document.document_type == Document.TYPE_INCOMING:
        return -document.total_amount
    return Decimal("0")


def _payment_balance_effect(payment: Payment) -> Decimal:
    # TODO LEGACY_RULE_REQUIRED: confirm refund direction and payment-to-document matching rules.
    if payment.status != Payment.STATUS_POSTED:
        return Decimal("0")
    if payment.payment_type == Payment.TYPE_CUSTOMER_PAYMENT:
        return -payment.amount
    if payment.payment_type == Payment.TYPE_SUPPLIER_PAYMENT:
        return payment.amount
    if payment.payment_type == Payment.TYPE_REFUND:
        return payment.amount
    return Decimal("0")


def _validate_payment_partner(db: Session, payment_type: str, partner_id: int) -> None:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    if payment_type == Payment.TYPE_CUSTOMER_PAYMENT and partner.partner_type not in {Partner.TYPE_CUSTOMER, Partner.TYPE_BOTH}:
        raise HTTPException(status_code=409, detail="Customer payment requires customer partner")
    if payment_type == Payment.TYPE_SUPPLIER_PAYMENT and partner.partner_type not in {Partner.TYPE_SUPPLIER, Partner.TYPE_BOTH}:
        raise HTTPException(status_code=409, detail="Supplier payment requires supplier partner")


def _validate_supported_payment(payment_type: str, method: str | None) -> None:
    if payment_type not in _valid_payment_types():
        raise HTTPException(status_code=422, detail="Payment type is not enabled for the first release")
    if method != "cash":
        raise HTTPException(status_code=422, detail="Only cash payments are enabled for the first release")


def _validate_payment_document(
    db: Session,
    payment_type: str,
    partner_id: int,
    document_id: int | None,
) -> None:
    if document_id is None:
        return
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != Document.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Payment requires posted document")
    if document.partner_id != partner_id:
        raise HTTPException(status_code=409, detail="Payment partner must match document partner")
    expected_document_type = {
        Payment.TYPE_CUSTOMER_PAYMENT: Document.TYPE_OUTGOING,
        Payment.TYPE_SUPPLIER_PAYMENT: Document.TYPE_INCOMING,
    }.get(payment_type)
    if expected_document_type and document.document_type != expected_document_type:
        raise HTTPException(status_code=409, detail="Document type does not match payment type")


def _allocation_inputs_from_payment(payment: Payment) -> list[PaymentAllocationInput]:
    return [
        PaymentAllocationInput(document_id=allocation.document_id, amount=allocation.amount)
        for allocation in payment.allocations
    ]


def _posted_allocated_amount(
    db: Session,
    document_id: int,
    *,
    exclude_payment_id: int | None = None,
) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.document_id == document_id,
            Payment.status == Payment.STATUS_POSTED,
        )
    )
    if exclude_payment_id is not None:
        statement = statement.where(Payment.id != exclude_payment_id)
    return Decimal(db.scalar(statement) or 0)


def _validate_allocations(
    db: Session,
    payment_type: str,
    partner_id: int,
    payment_amount: Decimal,
    allocations: list[PaymentAllocationInput],
    *,
    exclude_payment_id: int | None = None,
    lock_documents: bool = False,
) -> list[tuple[Document, Decimal]]:
    if payment_type == Payment.TYPE_REFUND and allocations:
        raise HTTPException(status_code=422, detail="Refund cannot be allocated to documents")
    document_ids = [allocation.document_id for allocation in allocations]
    if len(document_ids) != len(set(document_ids)):
        raise HTTPException(status_code=422, detail="Payment document can be allocated only once")
    allocated_total = sum((allocation.amount for allocation in allocations), Decimal("0"))
    if allocated_total > payment_amount:
        raise HTTPException(status_code=409, detail="Allocated amount exceeds payment amount")

    documents: dict[int, Document] = {}
    if document_ids:
        statement = select(Document).where(Document.id.in_(sorted(document_ids))).order_by(Document.id)
        if lock_documents:
            statement = statement.with_for_update()
        documents = {document.id: document for document in db.scalars(statement).all()}
    validated: list[tuple[Document, Decimal]] = []
    for allocation in allocations:
        document = documents.get(allocation.document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        _validate_payment_document(db, payment_type, partner_id, document.id)
        already_allocated = _posted_allocated_amount(
            db,
            document.id,
            exclude_payment_id=exclude_payment_id,
        )
        outstanding = max(document.total_amount - already_allocated, Decimal("0"))
        if allocation.amount > outstanding:
            raise HTTPException(
                status_code=409,
                detail=f"Allocation exceeds outstanding amount for document {document.number or document.id}",
            )
        validated.append((document, allocation.amount))
    return validated


def _replace_allocations(
    db: Session,
    payment: Payment,
    validated: list[tuple[Document, Decimal]],
) -> None:
    payment.allocations.clear()
    db.flush()
    payment.allocations = [
        PaymentAllocation(document_id=document.id, amount=amount, document=document)
        for document, amount in validated
    ]
    payment.document_id = validated[0][0].id if len(validated) == 1 else None


def get_payment_allocation_options(
    db: Session,
    partner_id: int,
    payment_type: str,
    *,
    exclude_payment_id: int | None = None,
) -> list[PaymentAllocationOption]:
    _validate_supported_payment(payment_type, "cash")
    _validate_payment_partner(db, payment_type, partner_id)
    expected_document_type = {
        Payment.TYPE_CUSTOMER_PAYMENT: Document.TYPE_OUTGOING,
        Payment.TYPE_SUPPLIER_PAYMENT: Document.TYPE_INCOMING,
    }.get(payment_type)
    if expected_document_type is None:
        return []
    documents = db.scalars(
        select(Document)
        .where(
            Document.partner_id == partner_id,
            Document.document_type == expected_document_type,
            Document.status == Document.STATUS_POSTED,
        )
        .order_by(Document.document_date, Document.id)
    ).all()
    options: list[PaymentAllocationOption] = []
    for document in documents:
        allocated = _posted_allocated_amount(db, document.id, exclude_payment_id=exclude_payment_id)
        outstanding = max(document.total_amount - allocated, Decimal("0"))
        if outstanding <= 0:
            continue
        options.append(
            PaymentAllocationOption(
                document_id=document.id,
                document_number=document.number,
                document_date=document.document_date,
                total_amount=document.total_amount,
                allocated_amount=allocated,
                outstanding_amount=outstanding,
            )
        )
    return options


def _valid_payment_types() -> set[str]:
    return {
        Payment.TYPE_CUSTOMER_PAYMENT,
        Payment.TYPE_SUPPLIER_PAYMENT,
    }


def _ensure_draft(payment: Payment) -> None:
    if payment.status != Payment.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft payments can be edited")


def create_payment(db: Session, payload: PaymentCreate) -> Payment:
    _validate_supported_payment(payload.payment_type, payload.method)
    _validate_payment_partner(db, payload.payment_type, payload.partner_id)
    allocation_inputs = list(payload.allocations)
    if not allocation_inputs and payload.document_id is not None:
        allocation_inputs = [PaymentAllocationInput(document_id=payload.document_id, amount=payload.amount)]
    validated_allocations = _validate_allocations(
        db,
        payload.payment_type,
        payload.partner_id,
        payload.amount,
        allocation_inputs,
    )
    values = payload.model_dump(exclude={"status", "allocations", "document_id"})
    payment = Payment(**values, status=Payment.STATUS_DRAFT)
    db.add(payment)
    db.flush()
    _replace_allocations(db, payment, validated_allocations)
    write_audit(db, "payment", payment.id, "create")
    db.commit()
    db.refresh(payment)
    return payment


def update_payment(db: Session, payment_id: int, payload: PaymentUpdate) -> Payment:
    payment = _load_payment(db, payment_id)
    _ensure_draft(payment)
    values = payload.model_dump(exclude_unset=True, exclude={"allocations", "document_id"})
    next_payment_type = values.get("payment_type", payment.payment_type)
    next_partner_id = values.get("partner_id", payment.partner_id)
    next_method = values.get("method", payment.method)
    _validate_supported_payment(next_payment_type, next_method)
    _validate_payment_partner(db, next_payment_type, next_partner_id)
    next_amount = values.get("amount", payment.amount)
    if payload.allocations is not None:
        allocation_inputs = list(payload.allocations)
    elif "document_id" in payload.model_fields_set:
        allocation_inputs = (
            [PaymentAllocationInput(document_id=payload.document_id, amount=next_amount)]
            if payload.document_id is not None
            else []
        )
    else:
        allocation_inputs = _allocation_inputs_from_payment(payment)
    validated_allocations = _validate_allocations(
        db,
        next_payment_type,
        next_partner_id,
        next_amount,
        allocation_inputs,
    )
    old_values = {key: getattr(payment, key) for key in values}
    for key, value in values.items():
        setattr(payment, key, value)
    _replace_allocations(db, payment, validated_allocations)
    new_values = {key: getattr(payment, key) for key in values}
    write_audit(db, "payment", payment.id, "update", change_details(old_values, new_values))
    db.commit()
    db.refresh(payment)
    return payment


def delete_draft_payment(db: Session, payment_id: int) -> None:
    payment = _load_payment(db, payment_id)
    if payment.status != Payment.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft payments can be deleted")
    write_audit(db, "payment", payment.id, "delete_draft")
    db.delete(payment)
    db.commit()


def post_payment(db: Session, payment_id: int) -> Payment:
    payment = _load_payment(db, payment_id, for_update=True)
    if payment.status != Payment.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft payments can be posted")
    _validate_supported_payment(payment.payment_type, payment.method)
    _validate_payment_partner(db, payment.payment_type, payment.partner_id)
    try:
        validated_allocations = _validate_allocations(
            db,
            payment.payment_type,
            payment.partner_id,
            payment.amount,
            _allocation_inputs_from_payment(payment),
            lock_documents=True,
        )
        payment.document_id = validated_allocations[0][0].id if len(validated_allocations) == 1 else None
        payment.status = Payment.STATUS_POSTED
        # TODO LEGACY_RULE_REQUIRED: refund cash direction must be confirmed against legacy cash rules.
        cash_operation_type = CashOperation.TYPE_CASH_IN
        if payment.payment_type in {Payment.TYPE_SUPPLIER_PAYMENT, Payment.TYPE_REFUND}:
            cash_operation_type = CashOperation.TYPE_CASH_OUT
        cash_service.create_cash_operation(
            db,
            CashOperationInternalCreate(
                operation_date=payment.payment_date,
                operation_type=cash_operation_type,
                amount=payment.amount,
                partner_id=payment.partner_id,
                document_id=payment.document_id,
                payment_id=payment.id,
                note=f"payment:{payment.payment_type}",
            ),
            commit=False,
        )
        write_audit(
            db,
            "payment",
            payment.id,
            "post",
            change_details({"status": Payment.STATUS_DRAFT}, {"status": Payment.STATUS_POSTED}),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    db.refresh(payment)
    return payment


def replace_posted_payment_allocations(
    db: Session,
    payment_id: int,
    allocations: list[PaymentAllocationInput],
) -> Payment:
    payment = _load_payment(db, payment_id, for_update=True)
    if payment.status != Payment.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted payments can be reallocated")
    old_values = [
        {"document_id": allocation.document_id, "amount": str(allocation.amount)}
        for allocation in payment.allocations
    ]
    try:
        validated = _validate_allocations(
            db,
            payment.payment_type,
            payment.partner_id,
            payment.amount,
            allocations,
            exclude_payment_id=payment.id,
            lock_documents=True,
        )
        _replace_allocations(db, payment, validated)
        for cash_operation in payment.cash_operations:
            cash_operation.document_id = payment.document_id
        new_values = [
            {"document_id": document.id, "amount": str(amount)}
            for document, amount in validated
        ]
        write_audit(
            db,
            "payment",
            payment.id,
            "allocate",
            change_details({"allocations": old_values}, {"allocations": new_values}),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    db.expire_all()
    return _load_payment(db, payment_id)


def cancel_payment(db: Session, payment_id: int) -> Payment:
    payment = _load_payment(db, payment_id, for_update=True)
    if payment.status != Payment.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted payments can be cancelled")
    try:
        cash_service.cancel_payment_cash_operations(db, payment.id)
        payment.status = Payment.STATUS_CANCELLED
        # TODO LEGACY_RULE_REQUIRED: confirm if legacy posts a reversing cash row on payment cancellation.
        write_audit(
            db,
            "payment",
            payment.id,
            "cancel",
            change_details({"status": Payment.STATUS_POSTED}, {"status": Payment.STATUS_CANCELLED}),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    db.refresh(payment)
    return payment


def get_partner_balance(db: Session, partner_id: int) -> PartnerBalanceRead:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    balance = Decimal("0")
    for document in db.scalars(select(Document).where(Document.partner_id == partner_id)):
        balance += _document_balance_effect(document)
    for payment in db.scalars(select(Payment).where(Payment.partner_id == partner_id)):
        balance += _payment_balance_effect(payment)
    return PartnerBalanceRead(partner_id=partner.id, partner_name=partner.name, partner_type=partner.partner_type, balance=balance)


def get_partner_balances(db: Session) -> list[PartnerBalanceRead]:
    return [get_partner_balance(db, partner.id) for partner in db.scalars(select(Partner).order_by(Partner.name))]


def get_partner_statement(db: Session, partner_id: int) -> list[PartnerStatementRow]:
    if db.get(Partner, partner_id) is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    raw_rows: list[tuple[date, str, int, str | None, Decimal, Decimal, str]] = []
    for document in db.scalars(select(Document).where(Document.partner_id == partner_id)):
        effect = _document_balance_effect(document)
        debit = effect if effect > 0 else Decimal("0")
        credit = -effect if effect < 0 else Decimal("0")
        raw_rows.append((document.document_date, "document", document.id, document.number, debit, credit, document.status))
    for payment in db.scalars(select(Payment).where(Payment.partner_id == partner_id)):
        effect = _payment_balance_effect(payment)
        debit = effect if effect > 0 else Decimal("0")
        credit = -effect if effect < 0 else Decimal("0")
        raw_rows.append((payment.payment_date, "payment", payment.id, payment.document_number, debit, credit, payment.status))
    raw_rows.sort(key=lambda row: (row[0], row[1], row[2]))
    balance = Decimal("0")
    statement: list[PartnerStatementRow] = []
    for row_date, source_type, source_id, source_number, debit, credit, status in raw_rows:
        balance += debit - credit
        statement.append(
            PartnerStatementRow(
                date=row_date,
                source_type=source_type,
                source_id=source_id,
                source_number=source_number,
                debit=debit,
                credit=credit,
                balance=balance,
                status=status,
            )
        )
    return statement
