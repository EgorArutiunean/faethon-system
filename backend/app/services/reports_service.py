from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import CashOperation
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement
from app.schemas.reports import (
    CashBookReport,
    CashBookReportRow,
    DocumentsRegisterReport,
    DocumentsRegisterReportRow,
    PartnerDebtsReport,
    PartnerDebtsReportRow,
    StockBalancesReport,
    StockBalancesReportRow,
    StockMovementsReport,
    StockMovementsReportRow,
)
from app.services.cash_service import get_cash_balance
from app.services.payments_service import get_partner_balance


def _date_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _date_end(value: date) -> datetime:
    return datetime.combine(value, time.max)


def stock_balances_report(
    db: Session,
    *,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
) -> StockBalancesReport:
    stmt = select(StockBalance).options(selectinload(StockBalance.product), selectinload(StockBalance.warehouse))
    if warehouse_id is not None:
        stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(StockBalance.product_id == product_id)
    if search:
        stmt = stmt.join(Product).where(Product.name.ilike(f"%{search}%"))

    rows = [
        StockBalancesReportRow(
            product_id=item.product_id,
            product_name=item.product_name,
            warehouse_id=item.warehouse_id,
            warehouse_name=item.warehouse_name,
            quantity=item.quantity,
        )
        for item in db.scalars(stmt.order_by(StockBalance.warehouse_id, StockBalance.product_id))
    ]
    return StockBalancesReport(rows=rows, total_quantity=sum((row.quantity for row in rows), Decimal("0")))


def stock_movements_report(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    document_id: int | None = None,
) -> StockMovementsReport:
    stmt = select(StockMovement).options(
        selectinload(StockMovement.product),
        selectinload(StockMovement.warehouse),
        selectinload(StockMovement.document),
    )
    if date_from is not None:
        stmt = stmt.where(StockMovement.created_at >= _date_start(date_from))
    if date_to is not None:
        stmt = stmt.where(StockMovement.created_at <= _date_end(date_to))
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if document_id is not None:
        stmt = stmt.where(StockMovement.document_id == document_id)

    rows = [
        StockMovementsReportRow(
            id=item.id,
            created_at=item.created_at,
            product_id=item.product_id,
            product_name=item.product_name,
            warehouse_id=item.warehouse_id,
            warehouse_name=item.warehouse_name,
            document_id=item.document_id,
            document_number=item.document_number,
            document_type=item.document.document_type if item.document else None,
            status=item.document.status if item.document else None,
            movement_type=item.movement_type,
            quantity_delta=item.quantity_delta,
        )
        for item in db.scalars(stmt.order_by(StockMovement.created_at, StockMovement.id))
    ]
    return StockMovementsReport(rows=rows, total_quantity=sum((row.quantity_delta for row in rows), Decimal("0")))


def partner_debts_report(
    db: Session,
    *,
    partner_id: int | None = None,
    partner_type: str | None = None,
    only_with_balance: bool = False,
) -> PartnerDebtsReport:
    stmt = select(Partner).order_by(Partner.name)
    if partner_id is not None:
        stmt = stmt.where(Partner.id == partner_id)
    if partner_type:
        stmt = stmt.where(Partner.partner_type == partner_type)

    rows: list[PartnerDebtsReportRow] = []
    for partner in db.scalars(stmt):
        balance = get_partner_balance(db, partner.id).balance
        if only_with_balance and balance == Decimal("0"):
            continue
        rows.append(PartnerDebtsReportRow(partner_id=partner.id, partner_name=partner.name, partner_type=partner.partner_type, balance=balance))
    return PartnerDebtsReport(rows=rows, total_partner_debt=sum((row.balance for row in rows), Decimal("0")))


def _cash_effect(operation: CashOperation) -> Decimal:
    if operation.status == CashOperation.STATUS_CANCELLED:
        return Decimal("0")
    if operation.operation_type == CashOperation.TYPE_CASH_IN:
        return operation.amount
    if operation.operation_type == CashOperation.TYPE_CASH_OUT:
        return -operation.amount
    # TODO LEGACY_RULE_REQUIRED: confirm whether correction is a signed delta or absolute target balance.
    return operation.amount


def cash_book_report(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    operation_type: str | None = None,
    status: str | None = None,
) -> CashBookReport:
    stmt = select(CashOperation).options(selectinload(CashOperation.partner), selectinload(CashOperation.payment))
    if date_from is not None:
        stmt = stmt.where(CashOperation.operation_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CashOperation.operation_date <= date_to)
    if operation_type:
        stmt = stmt.where(CashOperation.operation_type == operation_type)
    if status:
        stmt = stmt.where(CashOperation.status == status)

    running_balance = Decimal("0")
    cash_in_total = Decimal("0")
    cash_out_total = Decimal("0")
    rows: list[CashBookReportRow] = []
    for item in db.scalars(stmt.order_by(CashOperation.operation_date, CashOperation.id)):
        effect = _cash_effect(item)
        running_balance += effect
        if item.status != CashOperation.STATUS_CANCELLED and item.operation_type == CashOperation.TYPE_CASH_IN:
            cash_in_total += item.amount
        if item.status != CashOperation.STATUS_CANCELLED and item.operation_type == CashOperation.TYPE_CASH_OUT:
            cash_out_total += item.amount
        rows.append(
            CashBookReportRow(
                id=item.id,
                operation_date=item.operation_date,
                operation_type=item.operation_type,
                status=item.status,
                amount=item.amount,
                partner_id=item.partner_id,
                partner_name=item.partner_name,
                payment_id=item.payment_id,
                document_id=item.document_id,
                cash_balance=running_balance,
            )
        )
    return CashBookReport(
        rows=rows,
        cash_in_total=cash_in_total,
        cash_out_total=cash_out_total,
        cash_balance=get_cash_balance(db).balance,
    )


def documents_register_report(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    document_type: str | None = None,
    status: str | None = None,
    partner_id: int | None = None,
    warehouse_id: int | None = None,
) -> DocumentsRegisterReport:
    stmt = select(Document).options(selectinload(Document.partner), selectinload(Document.warehouse), selectinload(Document.destination_warehouse))
    if date_from is not None:
        stmt = stmt.where(Document.document_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Document.document_date <= date_to)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if status:
        stmt = stmt.where(Document.status == status)
    if partner_id is not None:
        stmt = stmt.where(Document.partner_id == partner_id)
    if warehouse_id is not None:
        stmt = stmt.where(Document.warehouse_id == warehouse_id)

    rows = [
        DocumentsRegisterReportRow(
            id=item.id,
            document_number=item.number,
            document_date=item.document_date,
            document_type=item.document_type,
            status=item.status,
            partner_id=item.partner_id,
            partner_name=item.partner_name,
            warehouse_id=item.warehouse_id,
            warehouse_name=item.warehouse_name,
            destination_warehouse_id=item.destination_warehouse_id,
            destination_warehouse_name=item.destination_warehouse_name,
            total_amount=item.total_amount,
        )
        for item in db.scalars(stmt.order_by(Document.document_date, Document.id))
    ]
    return DocumentsRegisterReport(rows=rows, total_amount=sum((row.total_amount for row in rows), Decimal("0")))
