from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Timestamped


CASH_OPERATION_TYPES = {"cash_in", "cash_out", "correction"}
CASH_OPERATION_STATUSES = {"posted", "cancelled"}


class CashOperationBase(BaseModel):
    operation_date: date
    operation_type: str
    amount: Decimal = Field(ge=0)
    partner_id: int | None = None
    document_id: int | None = None
    note: str | None = None


class CashOperationCreate(CashOperationBase):
    model_config = ConfigDict(extra="forbid")


class CashOperationInternalCreate(CashOperationBase):
    payment_id: int | None = None


class CashOperationRead(CashOperationBase, Timestamped):
    id: int
    direction: str
    status: str
    target_balance: Decimal | None = None
    payment_id: int | None = None
    created_by_id: int | None = None
    partner_name: str | None = None
    payment_status: str | None = None


class CashBalanceRead(BaseModel):
    balance: Decimal


class CashBookRow(CashOperationRead):
    balance: Decimal
