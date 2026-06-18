from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.currencies import CurrencyRead, ExchangeRateCreate, ExchangeRateRead
from app.services import currency_service

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyRead], dependencies=[Depends(require_permission("documents.read"))])
def list_currencies(db: Session = Depends(get_db)):
    return currency_service.list_currencies(db)


@router.get("/rates", response_model=list[ExchangeRateRead], dependencies=[Depends(require_permission("documents.read"))])
def list_exchange_rates(currency_code: str | None = None, db: Session = Depends(get_db)):
    return currency_service.list_exchange_rates(db, currency_code)


@router.post("/rates", response_model=ExchangeRateRead, dependencies=[Depends(require_permission("settings.manage"))])
def create_exchange_rate(payload: ExchangeRateCreate, db: Session = Depends(get_db)):
    return currency_service.create_exchange_rate(db, payload)


@router.get("/rates/latest", dependencies=[Depends(require_permission("documents.read"))])
def latest_exchange_rate(currency_code: str, on_date: date | None = None, db: Session = Depends(get_db)):
    return {"currency_code": currency_code, "rate_to_base": currency_service.latest_rate(db, currency_code, on_date)}
