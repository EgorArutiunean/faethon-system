from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.documents import DocumentRead


class DashboardWarehouseTotal(BaseModel):
    name: str
    quantity: Decimal


class DashboardSummary(BaseModel):
    date_from: date | None = None
    products_count: int | None = None
    partners_count: int | None = None
    documents_count: int | None = None
    outgoing_total: Decimal | None = None
    incoming_total: Decimal | None = None
    document_statuses: dict[str, int] | None = None
    document_types: dict[str, int] | None = None
    payment_statuses: dict[str, int] | None = None
    stock_positions_count: int | None = None
    stock_total_quantity: Decimal | None = None
    top_warehouses: list[DashboardWarehouseTotal] | None = None
    cash_balance: Decimal | None = None
    recent_documents: list[DocumentRead] | None = None
