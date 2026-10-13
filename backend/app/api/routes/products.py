from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.products import Product
from app.schemas.products import (
    ProductCreate,
    ProductGroupCounts,
    ProductPage,
    ProductRead,
    ProductUpdate,
)
from app.services import directory_service, product_pricing_service
from app.services.crud import CRUDService

router = APIRouter(prefix="/products", tags=["products"])
service = CRUDService[Product, ProductCreate, ProductUpdate](Product)


@router.get(
    "",
    response_model=list[ProductRead],
    dependencies=[Depends(require_permission("products.read"))],
)
def list_products(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    search: str | None = None,
):
    stmt = (
        select(Product)
        .options(selectinload(Product.group))
        .order_by(Product.name, Product.id)
        .offset(skip)
        .limit(limit)
    )
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    return product_pricing_service.attach_product_pricing(db, list(db.scalars(stmt).all()))


@router.get(
    "/page", response_model=ProductPage, dependencies=[Depends(require_permission("products.read"))]
)
def page_products(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    sort_by: Literal["name", "sku", "base_price", "created_at", "is_active"] = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    group_ids: list[int] | None = Query(default=None),
):
    filters = []
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if group_ids:
        filters.append(Product.group_id.in_(set(group_ids)))

    total = db.scalar(select(func.count(Product.id)).where(*filters)) or 0
    sort_column = getattr(Product, sort_by)
    order = desc(sort_column) if sort_order == "desc" else asc(sort_column)
    stmt = (
        select(Product)
        .options(selectinload(Product.group))
        .where(*filters)
        .order_by(order, Product.id)
        .offset(offset)
        .limit(limit)
    )
    products = product_pricing_service.attach_product_pricing(db, list(db.scalars(stmt).all()))
    return ProductPage(items=products, total=total, offset=offset, limit=limit)


@router.get(
    "/options",
    response_model=list[ProductRead],
    dependencies=[Depends(require_permission("products.read"))],
)
def product_options(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
):
    stmt = select(Product).options(selectinload(Product.group)).where(Product.is_active.is_(True))
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    stmt = stmt.order_by(Product.name, Product.id).limit(limit)
    return product_pricing_service.attach_product_pricing(db, list(db.scalars(stmt).all()))


@router.get(
    "/group-counts",
    response_model=ProductGroupCounts,
    dependencies=[Depends(require_permission("products.read"))],
)
def product_group_counts(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Product.id))) or 0
    rows = db.execute(
        select(Product.group_id, func.count(Product.id))
        .where(Product.group_id.is_not(None))
        .group_by(Product.group_id)
    ).all()
    return ProductGroupCounts(
        total=total,
        items=[{"group_id": group_id, "count": count} for group_id, count in rows],
    )


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("products.create"))],
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    return product_pricing_service.attach_single_product_pricing(
        db,
        directory_service.create_product(db, payload),
    )


@router.get(
    "/{item_id}",
    response_model=ProductRead,
    dependencies=[Depends(require_permission("products.read"))],
)
def get_product(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_pricing_service.attach_single_product_pricing(db, obj)


@router.patch(
    "/{item_id}",
    response_model=ProductRead,
    dependencies=[Depends(require_permission("products.update"))],
)
def update_product(item_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_pricing_service.attach_single_product_pricing(
        db,
        directory_service.update_product(db, obj, payload),
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("products.delete"))],
)
def delete_product(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    directory_service.delete_product(db, obj)
