from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InventoryOpening(Base):
    __tablename__ = "inventory_openings"
    __table_args__ = (
        UniqueConstraint(
            "batch_key",
            "product_id",
            "warehouse_id",
            name="uq_inventory_opening_batch_product_warehouse",
        ),
        CheckConstraint(
            "quantity >= 0 AND unit_cost >= 0 AND amount >= 0 AND sale_price >= 0",
            name="ck_inventory_opening_nonnegative",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_key: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    effective_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    sale_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str] = mapped_column(String(12))
    source_data: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
