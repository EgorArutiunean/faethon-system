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
