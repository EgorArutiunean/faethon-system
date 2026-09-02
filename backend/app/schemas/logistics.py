from datetime import date, datetime
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


class WarehouseTaskLineRead(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    expected_quantity: Decimal
    actual_quantity: Decimal | None = None
    status: str
    comment: str | None = None
    sale_price: Decimal
    sale_total: Decimal


class WarehouseTaskEventRead(BaseModel):
    id: int
    event_type: str
    actor_user_id: int | None = None
    actor_name: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    created_at: datetime


class WarehouseTaskRead(BaseModel):
    id: int
    document_id: int
    document_number: str | None = None
    document_date: date
    document_type: str
    posting_version: int
    partner_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    task_type: str
    status: str
    assigned_to_id: int | None = None
    assigned_to_name: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    lines: list[WarehouseTaskLineRead] = Field(default_factory=list)
    events: list[WarehouseTaskEventRead] = Field(default_factory=list)


class WarehouseTaskLineConfirmation(BaseModel):
    line_id: int
    actual_quantity: Decimal = Field(ge=0)
    comment: str | None = Field(default=None, max_length=1000)


class WarehouseTaskConfirmation(BaseModel):
    lines: list[WarehouseTaskLineConfirmation] = Field(min_length=1)


class WarehouseTaskReturn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)
