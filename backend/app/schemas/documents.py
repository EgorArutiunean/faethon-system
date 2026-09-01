from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped

DOCUMENT_STATUSES = {"draft", "posted", "cancelled"}
DOCUMENT_TYPES = {"incoming", "outgoing", "adjustment", "transfer"}


class DocumentBase(BaseModel):
    document_type: str
    number: str | None = None
    document_date: date
    status: str = "draft"
    partner_id: int | None = None
    warehouse_id: int | None = None
    destination_warehouse_id: int | None = None
    total_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency_code: str = "RUB_PMR"
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=0)
    foreign_total_amount: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    number: str | None = None
    document_date: date | None = None
    status: str | None = None
    partner_id: int | None = None
    warehouse_id: int | None = None
    destination_warehouse_id: int | None = None
    total_amount: Decimal | None = Field(default=None, ge=0)
    currency_code: str | None = None
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    foreign_total_amount: Decimal | None = Field(default=None, ge=0)
    note: str | None = None


class DocumentRead(DocumentBase, Timestamped):
    id: int
    partner_name: str | None = None
    warehouse_name: str | None = None
    destination_warehouse_name: str | None = None


class DocumentLineBase(BaseModel):
    product_id: int
    quantity: Decimal = Field(ge=0)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    foreign_price: Decimal | None = Field(default=None, ge=0)


class DocumentLineCreate(DocumentLineBase):
    pass


class DocumentLineUpdate(BaseModel):
    product_id: int | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, ge=0)
    foreign_price: Decimal | None = Field(default=None, ge=0)


class DocumentLineRead(DocumentLineBase, Timestamped):
    id: int
    document_id: int
    line_total: Decimal
    foreign_line_total: Decimal | None = None
    total: Decimal
    product_name: str | None = None


class DocumentDetailRead(DocumentRead):
    lines: list[DocumentLineRead] = []
