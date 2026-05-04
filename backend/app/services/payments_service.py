from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import AuditLog, CashOperation, Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.schemas.cash import CashOperationCreate
from app.schemas.payments import PaymentCreate, PartnerBalanceRead, PartnerStatementRow
from app.services import cash_service


def _audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, details=details))


def _load_payment(db: Session, payment_id: int) -> Payment:
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.partner), selectinload(Payment.document), selectinload(Payment.cash_operations))
    )
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
    # TODO LEGACY_RULE_REQUIRED: refund partner direction must be confirmed against legacy payment rules.


def create_payment(db: Session, payload: PaymentCreate) -> Payment:
    if payload.payment_type not in {
        Payment.TYPE_CUSTOMER_PAYMENT,
        Payment.TYPE_SUPPLIER_PAYMENT,
        Payment.TYPE_REFUND,
    }:
        raise HTTPException(status_code=422, detail="Invalid payment type")
    _validate_payment_partner(db, payload.payment_type, payload.partner_id)
    payment = Payment(**payload.model_dump(exclude={"status"}), status=Payment.STATUS_DRAFT)
    db.add(payment)
    db.flush()
    _audit(db, "payment", payment.id, "create")
    db.commit()
    db.refresh(payment)
    return payment


def post_payment(db: Session, payment_id: int) -> Payment:
    payment = _load_payment(db, payment_id)
    if payment.status != Payment.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft payments can be posted")
    _validate_payment_partner(db, payment.payment_type, payment.partner_id)
    payment.status = Payment.STATUS_POSTED
    # TODO LEGACY_RULE_REQUIRED: refund cash direction must be confirmed against legacy cash rules.
    cash_operation_type = CashOperation.TYPE_CASH_IN
    if payment.payment_type in {Payment.TYPE_SUPPLIER_PAYMENT, Payment.TYPE_REFUND}:
        cash_operation_type = CashOperation.TYPE_CASH_OUT
    cash_service.create_cash_operation(
        db,
        CashOperationCreate(
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
    _audit(db, "payment", payment.id, "post")
    db.commit()
    db.refresh(payment)
    return payment


def cancel_payment(db: Session, payment_id: int) -> Payment:
    payment = _load_payment(db, payment_id)
    if payment.status != Payment.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted payments can be cancelled")
    payment.status = Payment.STATUS_CANCELLED
    cash_service.cancel_payment_cash_operations(db, payment.id)
    # TODO LEGACY_RULE_REQUIRED: confirm if legacy posts a reversing cash row on payment cancellation.
    _audit(db, "payment", payment.id, "cancel")
    db.commit()
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
