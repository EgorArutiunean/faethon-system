from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import require_permission
from app.models.products import Product
from app.schemas.products import ProductCreate, ProductRead, ProductUpdate
from app.services import directory_service
from app.services.crud import CRUDService

router = APIRouter(prefix="/products", tags=["products"])
service = CRUDService[Product, ProductCreate, ProductUpdate](Product)


@router.get("", response_model=list[ProductRead], dependencies=[Depends(require_permission("products.read"))])
def list_products(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    search: str | None = None,
):
    return service.list(db, skip=skip, limit=limit, search=search)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products.create"))])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    return directory_service.create_product(db, payload)


@router.get("/{item_id}", response_model=ProductRead, dependencies=[Depends(require_permission("products.read"))])
def get_product(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    return obj


@router.patch("/{item_id}", response_model=ProductRead, dependencies=[Depends(require_permission("products.update"))])
def update_product(item_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    return directory_service.update_product(db, obj, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products.delete"))])
def delete_product(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    directory_service.delete_product(db, obj)
