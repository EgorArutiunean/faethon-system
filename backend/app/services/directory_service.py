from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import AuditLog, Payment
from app.models.documents import Document, DocumentLine
from app.models.partners import Partner
from app.models.products import Product, ProductGroup
from app.models.stock import StockBalance, StockMovement, Warehouse
from app.schemas.partners import PartnerCreate, PartnerUpdate
from app.schemas.products import ProductCreate, ProductGroupCreate, ProductGroupUpdate, ProductUpdate
from app.schemas.warehouses import WarehouseCreate, WarehouseUpdate


def _audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, details=details))


def create_product(db: Session, payload: ProductCreate) -> Product:
    if payload.group_id and db.get(ProductGroup, payload.group_id) is None:
        raise HTTPException(status_code=404, detail="Product group not found")
    product = Product(**payload.model_dump())
    db.add(product)
    db.flush()
    _audit(db, "product", product.id, "create")
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, payload: ProductUpdate) -> Product:
    values = payload.model_dump(exclude_unset=True)
    if values.get("group_id") and db.get(ProductGroup, values["group_id"]) is None:
        raise HTTPException(status_code=404, detail="Product group not found")
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


def list_product_groups(db: Session, search: str | None = None) -> list[ProductGroup]:
    stmt = select(ProductGroup)
    if search:
        stmt = stmt.where(ProductGroup.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(ProductGroup.name)
    return list(db.scalars(stmt).all())


def _ensure_group_name_is_free(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    stmt = select(ProductGroup).where(ProductGroup.name == name)
    if exclude_id is not None:
        stmt = stmt.where(ProductGroup.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Product group with this name already exists")


def _ensure_parent_exists(db: Session, parent_id: int | None, *, group_id: int | None = None) -> None:
    if parent_id is None:
        return
    if group_id is not None and parent_id == group_id:
        raise HTTPException(status_code=409, detail="Product group cannot be its own parent")
    if db.get(ProductGroup, parent_id) is None:
        raise HTTPException(status_code=404, detail="Parent product group not found")


def create_product_group(db: Session, payload: ProductGroupCreate) -> ProductGroup:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product group name is required")
    _ensure_group_name_is_free(db, name)
    _ensure_parent_exists(db, payload.parent_id)
    group = ProductGroup(name=name, parent_id=payload.parent_id)
    db.add(group)
    db.flush()
    _audit(db, "product_group", group.id, "create")
    db.commit()
    db.refresh(group)
    return group


def update_product_group(db: Session, group: ProductGroup, payload: ProductGroupUpdate) -> ProductGroup:
    values = payload.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is not None:
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise HTTPException(status_code=422, detail="Product group name is required")
        _ensure_group_name_is_free(db, values["name"], exclude_id=group.id)
    if "parent_id" in values:
        _ensure_parent_exists(db, values["parent_id"], group_id=group.id)
    for key, value in values.items():
        setattr(group, key, value)
    _audit(db, "product_group", group.id, "update", ",".join(sorted(values.keys())))
    db.commit()
    db.refresh(group)
    return group


def delete_product_group(db: Session, group: ProductGroup) -> None:
    used = any(
        [
            db.scalar(select(Product.id).where(Product.group_id == group.id).limit(1)),
            db.scalar(select(ProductGroup.id).where(ProductGroup.parent_id == group.id).limit(1)),
        ]
    )
    if used:
        raise HTTPException(status_code=409, detail="Product group is used by products or child groups and cannot be deleted")
    _audit(db, "product_group", group.id, "delete")
    db.delete(group)
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
