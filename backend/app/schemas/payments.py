from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import Timestamped


PAYMENT_STATUSES = {"draft", "posted", "cancelled"}
PAYMENT_TYPES = {"customer_payment", "supplier_payment", "refund"}


class PaymentBase(BaseModel):
    partner_id: int
    document_id: int | None = None
    payment_date: date
    payment_type: str = "customer_payment"
    status: str = "draft"
    amount: Decimal
    method: str | None = "cash"
    note: str | None = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    partner_id: int | None = None
    document_id: int | None = None
    payment_date: date | None = None
    payment_type: str | None = None
    amount: Decimal | None = None
    method: str | None = None
    note: str | None = None


class PaymentRead(PaymentBase, Timestamped):
    id: int
    partner_name: str | None = None
    document_number: str | None = None
    cash_operation_id: int | None = None
    cash_operation_status: str | None = None


class PartnerBalanceRead(BaseModel):
    partner_id: int
    partner_name: str
    partner_type: str
    balance: Decimal


class PartnerStatementRow(BaseModel):
    date: date | datetime
    source_type: str
    source_id: int
    source_number: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    balance: Decimal
    status: str
