from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import AuditLog, Currency, ExchangeRate
from app.schemas.currencies import ExchangeRateCreate

BASE_CURRENCY_CODE = "RUB_PMR"

DEFAULT_CURRENCIES = [
    (BASE_CURRENCY_CODE, "Рубль ПМР", "р.", True),
    ("MDL", "Молдавский лей", "L", False),
    ("USD", "Доллар США", "$", False),
    ("EUR", "Евро", "€", False),
]


def seed_default_currencies(db: Session) -> None:
    for code, name, symbol, is_base in DEFAULT_CURRENCIES:
        currency = db.scalar(select(Currency).where(Currency.code == code))
        if currency is None:
            currency = Currency(code=code, name=name, symbol=symbol, is_base=is_base, is_active=True)
            db.add(currency)
        else:
            currency.name = name
            currency.symbol = symbol
            currency.is_base = is_base
            currency.is_active = True
    db.flush()


def list_currencies(db: Session) -> list[Currency]:
    seed_default_currencies(db)
    db.commit()
    return list(db.scalars(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.is_base.desc(), Currency.code)).all())


def get_currency(db: Session, code: str) -> Currency:
    seed_default_currencies(db)
    currency = db.scalar(select(Currency).where(Currency.code == code))
    if currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


def create_exchange_rate(db: Session, payload: ExchangeRateCreate) -> ExchangeRate:
    currency = get_currency(db, payload.currency_code)
    if currency.is_base and payload.rate_to_base != Decimal("1"):
        raise HTTPException(status_code=422, detail="Base currency rate must be 1")
    if payload.rate_to_base <= 0:
        raise HTTPException(status_code=422, detail="Exchange rate must be greater than zero")
    rate = ExchangeRate(currency_id=currency.id, rate_date=payload.rate_date, rate_to_base=payload.rate_to_base, note=payload.note)
    db.add(rate)
    db.flush()
    db.add(AuditLog(entity_type="exchange_rate", entity_id=str(rate.id), action="create", details=f"{currency.code}={rate.rate_to_base}"))
    db.commit()
    db.refresh(rate)
    return rate


def list_exchange_rates(db: Session, currency_code: str | None = None) -> list[ExchangeRate]:
    seed_default_currencies(db)
    stmt = select(ExchangeRate).options(selectinload(ExchangeRate.currency)).order_by(ExchangeRate.rate_date.desc(), ExchangeRate.id.desc())
    if currency_code:
        currency = get_currency(db, currency_code)
        stmt = stmt.where(ExchangeRate.currency_id == currency.id)
    return list(db.scalars(stmt).all())


def latest_rate(db: Session, currency_code: str, on_date: date | None = None) -> Decimal:
    currency = get_currency(db, currency_code)
    if currency.is_base:
        return Decimal("1")
    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.currency_id == currency.id)
        .order_by(ExchangeRate.rate_date.desc(), ExchangeRate.id.desc())
    )
    if on_date is not None:
        stmt = stmt.where(ExchangeRate.rate_date <= on_date)
    rate = db.scalar(stmt.limit(1))
    if rate is None:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    return rate.rate_to_base
