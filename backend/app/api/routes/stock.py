from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.stock import StockBalance, StockMovement
from app.schemas.stock import StockBalanceRead, StockMovementRead

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/balances", response_model=list[StockBalanceRead], dependencies=[Depends(require_permission("stock.read"))])
def list_stock_balances(
    db: Session = Depends(get_db),
    warehouse_id: int | None = None,
    product_id: int | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
):
    stmt = select(StockBalance).options(selectinload(StockBalance.product), selectinload(StockBalance.warehouse))
    if warehouse_id is not None:
        stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(StockBalance.product_id == product_id)
    return list(db.scalars(stmt.offset(skip).limit(limit)).all())


@router.get("/movements", response_model=list[StockMovementRead], dependencies=[Depends(require_permission("stock.read"))])
def list_stock_movements(
    db: Session = Depends(get_db),
    warehouse_id: int | None = None,
    product_id: int | None = None,
    document_id: int | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
):
    stmt = select(StockMovement).options(
        selectinload(StockMovement.product),
        selectinload(StockMovement.warehouse),
        selectinload(StockMovement.document),
    )
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if document_id is not None:
        stmt = stmt.where(StockMovement.document_id == document_id)
    return list(db.scalars(stmt.offset(skip).limit(limit)).all())
