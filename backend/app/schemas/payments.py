from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


PAYMENT_STATUSES = {"draft", "posted", "cancelled"}
PAYMENT_TYPES = {"customer_payment", "supplier_payment", "refund"}


class PaymentBase(BaseModel):
    partner_id: int
    document_id: int | None = None
    payment_date: date
    payment_type: str = "customer_payment"
    status: str = "draft"
    amount: Decimal = Field(gt=0)
    method: str | None = "cash"
    note: str | None = None


class PaymentAllocationInput(BaseModel):
    document_id: int
    amount: Decimal = Field(gt=0)


class PaymentCreate(PaymentBase):
    allocations: list[PaymentAllocationInput] = Field(default_factory=list)


class PaymentUpdate(BaseModel):
    partner_id: int | None = None
    document_id: int | None = None
    payment_date: date | None = None
    payment_type: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    method: str | None = None
    note: str | None = None
    allocations: list[PaymentAllocationInput] | None = None


class PaymentAllocationRead(Timestamped):
    id: int
    payment_id: int
    document_id: int
    document_number: str | None = None
    document_date: date | None = None
    document_total: Decimal | None = None
    amount: Decimal


class PaymentRead(PaymentBase, Timestamped):
    id: int
    partner_name: str | None = None
    document_number: str | None = None
    cash_operation_id: int | None = None
    cash_operation_status: str | None = None
    allocations: list[PaymentAllocationRead] = Field(default_factory=list)
    allocated_amount: Decimal = Decimal("0")
    unallocated_amount: Decimal = Decimal("0")


class PaymentAllocationReplace(BaseModel):
    allocations: list[PaymentAllocationInput]


class PaymentAllocationOption(BaseModel):
    document_id: int
    document_number: str | None = None
    document_date: date
    total_amount: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal


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
