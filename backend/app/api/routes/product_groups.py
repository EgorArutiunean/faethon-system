from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.products import ProductGroup
from app.schemas.products import ProductGroupCreate, ProductGroupRead, ProductGroupUpdate
from app.services import directory_service

router = APIRouter(prefix="/product-groups", tags=["products"])


@router.get("", response_model=list[ProductGroupRead], dependencies=[Depends(require_permission("products.read"))])
def list_product_groups(db: Session = Depends(get_db), search: str | None = None):
    return directory_service.list_product_groups(db, search=search)


@router.post("", response_model=ProductGroupRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products.create"))])
def create_product_group(payload: ProductGroupCreate, db: Session = Depends(get_db)):
    return directory_service.create_product_group(db, payload)


@router.get("/{item_id}", response_model=ProductGroupRead, dependencies=[Depends(require_permission("products.read"))])
def get_product_group(item_id: int, db: Session = Depends(get_db)):
    group = db.get(ProductGroup, item_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Product group not found")
    return group


@router.patch("/{item_id}", response_model=ProductGroupRead, dependencies=[Depends(require_permission("products.update"))])
def update_product_group(item_id: int, payload: ProductGroupUpdate, db: Session = Depends(get_db)):
    group = db.get(ProductGroup, item_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Product group not found")
    return directory_service.update_product_group(db, group, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products.delete"))])
def delete_product_group(item_id: int, db: Session = Depends(get_db)):
    group = db.get(ProductGroup, item_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Product group not found")
    directory_service.delete_product_group(db, group)
