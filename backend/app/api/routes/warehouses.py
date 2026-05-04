from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.stock import Warehouse
from app.schemas.warehouses import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.services import directory_service
from app.services.crud import CRUDService

router = APIRouter(prefix="/warehouses", tags=["warehouses"])
service = CRUDService[Warehouse, WarehouseCreate, WarehouseUpdate](Warehouse)


@router.get("", response_model=list[WarehouseRead], dependencies=[Depends(require_permission("warehouses.read"))])
def list_warehouses(db: Session = Depends(get_db), skip: int = 0, limit: int = Query(default=100, le=500), search: str | None = None):
    return service.list(db, skip=skip, limit=limit, search=search)


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("warehouses.create"))])
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db)):
    return directory_service.create_warehouse(db, payload)


@router.get("/{item_id}", response_model=WarehouseRead, dependencies=[Depends(require_permission("warehouses.read"))])
def get_warehouse(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return obj


@router.patch("/{item_id}", response_model=WarehouseRead, dependencies=[Depends(require_permission("warehouses.update"))])
def update_warehouse(item_id: int, payload: WarehouseUpdate, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return directory_service.update_warehouse(db, obj, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("warehouses.delete"))])
def delete_warehouse(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    directory_service.delete_warehouse(db, obj)
