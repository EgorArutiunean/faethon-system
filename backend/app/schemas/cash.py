from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import Timestamped


CASH_OPERATION_TYPES = {"cash_in", "cash_out", "correction"}
CASH_OPERATION_STATUSES = {"posted", "cancelled"}


class CashOperationBase(BaseModel):
    operation_date: date
    operation_type: str
    amount: Decimal
    partner_id: int | None = None
    document_id: int | None = None
    payment_id: int | None = None
    created_by_id: int | None = None
    note: str | None = None


class CashOperationCreate(CashOperationBase):
    pass


class CashOperationRead(CashOperationBase, Timestamped):
    id: int
    direction: str
    status: str
    partner_name: str | None = None
    payment_status: str | None = None


class CashBalanceRead(BaseModel):
    balance: Decimal


class CashBookRow(CashOperationRead):
    balance: Decimal
