from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.cash import CashBalanceRead, CashBookRow, CashOperationCreate, CashOperationRead
from app.services import cash_service

router = APIRouter(prefix="/cash", tags=["cash"])


@router.get("/operations", response_model=list[CashOperationRead], dependencies=[Depends(require_permission("cash.read"))])
def list_cash_operations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
):
    return cash_service.list_cash_operations(db, skip=skip, limit=limit)


@router.post("/operations", response_model=CashOperationRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("cash.create"))])
def create_cash_operation(payload: CashOperationCreate, db: Session = Depends(get_db)):
    return cash_service.create_cash_operation(db, payload)


@router.post("/operations/{operation_id}/cancel", response_model=CashOperationRead, dependencies=[Depends(require_permission("cash.cancel"))])
def cancel_cash_operation(operation_id: int, db: Session = Depends(get_db)):
    return cash_service.cancel_cash_operation(db, operation_id)


@router.get("/balance", response_model=CashBalanceRead, dependencies=[Depends(require_permission("cash.read"))])
def get_cash_balance(db: Session = Depends(get_db)):
    return cash_service.get_cash_balance(db)


@router.get("/book", response_model=list[CashBookRow], dependencies=[Depends(require_permission("cash.read"))])
def get_cash_book(db: Session = Depends(get_db)):
    return cash_service.get_cash_book(db)
