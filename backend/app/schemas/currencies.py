from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import Timestamped


class CurrencyRead(Timestamped):
    id: int
    code: str
    name: str
    symbol: str | None = None
    is_base: bool
    is_active: bool


class ExchangeRateCreate(BaseModel):
    currency_code: str
    rate_date: date
    rate_to_base: Decimal
    note: str | None = None


class ExchangeRateRead(Timestamped):
    id: int
    currency_id: int
    currency_code: str | None = None
    rate_date: date
    rate_to_base: Decimal
    note: str | None = None
