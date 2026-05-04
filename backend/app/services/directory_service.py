from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import AuditLog, Payment
from app.models.documents import Document, DocumentLine
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement, Warehouse
from app.schemas.partners import PartnerCreate, PartnerUpdate
from app.schemas.products import ProductCreate, ProductUpdate
from app.schemas.warehouses import WarehouseCreate, WarehouseUpdate


def _audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, details=details))


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.flush()
    _audit(db, "product", product.id, "create")
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, payload: ProductUpdate) -> Product:
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(product, key, value)
    _audit(db, "product", product.id, "update", ",".join(sorted(values.keys())))
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    used = any(
        [
            db.scalar(select(DocumentLine.id).where(DocumentLine.product_id == product.id).limit(1)),
            db.scalar(select(StockBalance.id).where(StockBalance.product_id == product.id).limit(1)),
            db.scalar(select(StockMovement.id).where(StockMovement.product_id == product.id).limit(1)),
        ]
    )
    if used:
        raise HTTPException(status_code=409, detail="Product is used in documents or stock and cannot be deleted")
    _audit(db, "product", product.id, "delete")
    db.delete(product)
    db.commit()


def create_warehouse(db: Session, payload: WarehouseCreate) -> Warehouse:
    warehouse = Warehouse(**payload.model_dump())
    db.add(warehouse)
    db.flush()
    _audit(db, "warehouse", warehouse.id, "create")
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse(db: Session, warehouse: Warehouse, payload: WarehouseUpdate) -> Warehouse:
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(warehouse, key, value)
    _audit(db, "warehouse", warehouse.id, "update", ",".join(sorted(values.keys())))
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, warehouse: Warehouse) -> None:
    used = any(
        [
            db.scalar(select(Document.id).where(Document.warehouse_id == warehouse.id).limit(1)),
            db.scalar(select(StockBalance.id).where(StockBalance.warehouse_id == warehouse.id).limit(1)),
            db.scalar(select(StockMovement.id).where(StockMovement.warehouse_id == warehouse.id).limit(1)),
        ]
    )
    if used:
        raise HTTPException(status_code=409, detail="Warehouse is used in documents or stock and cannot be deleted")
    _audit(db, "warehouse", warehouse.id, "delete")
    db.delete(warehouse)
    db.commit()


def create_partner(db: Session, payload: PartnerCreate) -> Partner:
    partner = Partner(**payload.model_dump())
    db.add(partner)
    db.flush()
    _audit(db, "partner", partner.id, "create")
    db.commit()
    db.refresh(partner)
    return partner


def update_partner(db: Session, partner: Partner, payload: PartnerUpdate) -> Partner:
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(partner, key, value)
    _audit(db, "partner", partner.id, "update", ",".join(sorted(values.keys())))
    db.commit()
    db.refresh(partner)
    return partner


def delete_partner(db: Session, partner: Partner) -> None:
    used = any(
        [
            db.scalar(select(Document.id).where(Document.partner_id == partner.id).limit(1)),
            db.scalar(select(Payment.id).where(Payment.partner_id == partner.id).limit(1)),
        ]
    )
    if used:
        raise HTTPException(status_code=409, detail="Partner is used in documents or payments and cannot be deleted")
    _audit(db, "partner", partner.id, "delete")
    db.delete(partner)
    db.commit()
