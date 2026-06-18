from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import Timestamped


class ProductBase(BaseModel):
    sku: str | None = None
    name: str
    description: str | None = None
    group_id: int | None = None
    unit_id: int | None = None
    base_price: Decimal | None = None
    is_active: bool = True


class ProductGroupBase(BaseModel):
    name: str
    parent_id: int | None = None


class ProductGroupCreate(ProductGroupBase):
    pass


class ProductGroupUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None


class ProductGroupRead(ProductGroupBase, Timestamped):
    id: int
    parent_name: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    description: str | None = None
    group_id: int | None = None
    unit_id: int | None = None
    base_price: Decimal | None = None
    is_active: bool | None = None


class ProductRead(ProductBase, Timestamped):
    id: int
    group_name: str | None = None
