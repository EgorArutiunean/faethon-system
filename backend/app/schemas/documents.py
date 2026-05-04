from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import Timestamped

DOCUMENT_STATUSES = {"draft", "posted", "cancelled"}
DOCUMENT_TYPES = {"incoming", "outgoing", "adjustment"}


class DocumentBase(BaseModel):
    document_type: str
    number: str | None = None
    document_date: date
    status: str = "draft"
    partner_id: int | None = None
    warehouse_id: int | None = None
    total_amount: Decimal = Decimal("0")
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
    total_amount: Decimal | None = None
    note: str | None = None


class DocumentRead(DocumentBase, Timestamped):
    id: int
    partner_name: str | None = None
    warehouse_name: str | None = None


class DocumentLineBase(BaseModel):
    product_id: int
    quantity: Decimal
    price: Decimal


class DocumentLineCreate(DocumentLineBase):
    pass


class DocumentLineUpdate(BaseModel):
    product_id: int | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None


class DocumentLineRead(DocumentLineBase, Timestamped):
    id: int
    document_id: int
    line_total: Decimal
    total: Decimal
    product_name: str | None = None


class DocumentDetailRead(DocumentRead):
    lines: list[DocumentLineRead] = []
