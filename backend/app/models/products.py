from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class ProductGroup(TimestampMixin, Base):
    __tablename__ = "product_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("product_groups.id"))

    parent = relationship("ProductGroup", remote_side=[id])
    products = relationship("Product", back_populates="group")

    @property
    def parent_name(self) -> str | None:
        return self.parent.name if self.parent else None


class Unit(TimestampMixin, Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    short_name: Mapped[str] = mapped_column(String(20), unique=True)

    products = relationship("Product", back_populates="unit")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("product_groups.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    group = relationship("ProductGroup", back_populates="products")
    unit = relationship("Unit", back_populates="products")
    document_lines = relationship("DocumentLine", back_populates="product")

    @property
    def group_name(self) -> str | None:
        return self.group.name if self.group else None
