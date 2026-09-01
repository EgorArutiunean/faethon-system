from decimal import Decimal
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class ProductBase(BaseModel):
    sku: str | None = None
    name: str
    description: str | None = None
    group_id: int | None = None
    unit_id: int | None = None
    base_price: Decimal | None = Field(default=None, ge=0)
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
    base_price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductRead(ProductBase, Timestamped):
    id: int
    group_name: str | None = None
    latest_purchase_cost: Decimal | None = None
    latest_purchase_document_id: int | None = None
    latest_purchase_document_number: str | None = None
    latest_purchase_date: date | None = None
    markup_percent: Decimal | None = None
    minimum_sale_price: Decimal | None = None
    price_review_required: bool = False
