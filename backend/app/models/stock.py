from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Warehouse(TimestampMixin, Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)

    stock_balances = relationship("StockBalance", back_populates="warehouse")
    stock_movements = relationship("StockMovement", back_populates="warehouse")


class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str | None] = mapped_column(String(120))

    product = relationship("Product")
    warehouse = relationship("Warehouse", back_populates="stock_movements")
    document = relationship("Document")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None

    @property
    def document_number(self) -> str | None:
        return self.document.number if self.document else None

    @property
    def movement_type(self) -> str | None:
        return self.reason.split(":", 1)[0] if self.reason else None


class StockBalance(TimestampMixin, Base):
    __tablename__ = "stock_balances"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id", name="uq_stock_balance_product_warehouse"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    product = relationship("Product")
    warehouse = relationship("Warehouse", back_populates="stock_balances")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None
