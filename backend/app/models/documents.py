from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CANCELLED = "cancelled"

    TYPE_INCOMING = "incoming"
    TYPE_OUTGOING = "outgoing"
    TYPE_ADJUSTMENT = "adjustment"
    TYPE_TRANSFER = "transfer"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(60), index=True)
    number: Mapped[str | None] = mapped_column(String(80), index=True)
    document_date: Mapped[Date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(40), default=STATUS_DRAFT, index=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id"))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    destination_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    note: Mapped[str | None] = mapped_column(Text)

    partner = relationship("Partner", back_populates="documents")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    destination_warehouse = relationship("Warehouse", foreign_keys=[destination_warehouse_id])
    lines = relationship("DocumentLine", back_populates="document", cascade="all, delete-orphan")

    @property
    def partner_name(self) -> str | None:
        return self.partner.name if self.partner else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None

    @property
    def destination_warehouse_name(self) -> str | None:
        return self.destination_warehouse.name if self.destination_warehouse else None


class DocumentLine(TimestampMixin, Base):
    __tablename__ = "document_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    document = relationship("Document", back_populates="lines")
    product = relationship("Product", back_populates="document_lines")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def total(self) -> Decimal:
        return self.line_total
