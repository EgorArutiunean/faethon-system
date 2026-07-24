from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LogisticsDocumentLineRead(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    quantity: Decimal
    sale_price: Decimal
    sale_total: Decimal


class LogisticsDocumentRead(BaseModel):
    id: int
    document_type: str
    number: str | None = None
    document_date: date
    status: str
    partner_name: str | None = None
    warehouse_id: int | None = None
    warehouse_name: str | None = None
    destination_warehouse_id: int | None = None
    destination_warehouse_name: str | None = None
    lines: list[LogisticsDocumentLineRead] = Field(default_factory=list)
