from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import CashOperation, Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, Warehouse
from app.schemas.dashboard import DashboardSummary, DashboardWarehouseTotal
from app.schemas.documents import DocumentRead


def _counts(db: Session, column, *filters) -> dict[str, int]:
    return {
        str(key): int(count)
        for key, count in db.execute(select(column, func.count()).where(*filters).group_by(column))
    }


def get_dashboard_summary(
    db: Session,
    permissions: set[str],
    *,
    date_from: date | None,
    recent_limit: int,
) -> DashboardSummary:
    result = DashboardSummary(date_from=date_from)

    if "products.read" in permissions:
        result.products_count = db.scalar(select(func.count(Product.id))) or 0
    if "partners.read" in permissions:
        result.partners_count = db.scalar(select(func.count(Partner.id))) or 0

    if "documents.read" in permissions:
        document_filters = [Document.document_date >= date_from] if date_from else []
        result.documents_count = (
            db.scalar(select(func.count(Document.id)).where(*document_filters)) or 0
        )
        result.outgoing_total = db.scalar(
            select(func.coalesce(func.sum(Document.total_amount), 0)).where(
                *document_filters,
                Document.status == Document.STATUS_POSTED,
                Document.document_type == Document.TYPE_OUTGOING,
            )
        ) or Decimal("0")
        result.incoming_total = db.scalar(
            select(func.coalesce(func.sum(Document.total_amount), 0)).where(
                *document_filters,
                Document.status == Document.STATUS_POSTED,
                Document.document_type == Document.TYPE_INCOMING,
            )
        ) or Decimal("0")
        result.document_statuses = _counts(db, Document.status, *document_filters)
        result.document_types = _counts(db, Document.document_type, *document_filters)
        recent_stmt = (
            select(Document)
            .options(
                selectinload(Document.partner),
                selectinload(Document.warehouse),
                selectinload(Document.destination_warehouse),
            )
            .where(*document_filters)
            .order_by(Document.document_date.desc(), Document.id.desc())
            .limit(recent_limit)
        )
        result.recent_documents = [
            DocumentRead.model_validate(document) for document in db.scalars(recent_stmt).all()
        ]

    if "payments.read" in permissions:
        payment_filters = [Payment.payment_date >= date_from] if date_from else []
        result.payment_statuses = _counts(db, Payment.status, *payment_filters)

    if "stock.read" in permissions:
        result.stock_positions_count = db.scalar(select(func.count(StockBalance.id))) or 0
        result.stock_total_quantity = db.scalar(
            select(func.coalesce(func.sum(StockBalance.quantity), 0))
        ) or Decimal("0")
        quantity = func.sum(StockBalance.quantity).label("quantity")
        warehouse_rows = db.execute(
            select(Warehouse.name, quantity)
            .join(StockBalance, StockBalance.warehouse_id == Warehouse.id)
            .group_by(Warehouse.id, Warehouse.name)
            .order_by(quantity.desc(), Warehouse.name)
            .limit(5)
        ).all()
        result.top_warehouses = [
            DashboardWarehouseTotal(name=name, quantity=value) for name, value in warehouse_rows
        ]

    if "cash.read" in permissions:
        cash_effect = case(
            (CashOperation.status == CashOperation.STATUS_CANCELLED, 0),
            (CashOperation.operation_type == CashOperation.TYPE_CASH_IN, CashOperation.amount),
            (CashOperation.operation_type == CashOperation.TYPE_CASH_OUT, -CashOperation.amount),
            (
                (CashOperation.operation_type == CashOperation.TYPE_CORRECTION)
                & (CashOperation.direction == "out"),
                -CashOperation.amount,
            ),
            (CashOperation.operation_type == CashOperation.TYPE_CORRECTION, CashOperation.amount),
            else_=0,
        )
        result.cash_balance = db.scalar(select(func.coalesce(func.sum(cash_effect), 0))) or Decimal(
            "0"
        )

    return result
