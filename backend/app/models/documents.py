from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("number", name="uq_documents_number"),
        CheckConstraint("total_amount >= 0", name="ck_documents_total_nonnegative"),
        CheckConstraint("foreign_total_amount >= 0", name="ck_documents_foreign_total_nonnegative"),
        CheckConstraint("exchange_rate > 0", name="ck_documents_exchange_rate_positive"),
        CheckConstraint("posting_version >= 0", name="ck_documents_posting_version_nonnegative"),
    )

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
    currency_code: Mapped[str] = mapped_column(String(12), default="RUB_PMR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=1)
    foreign_total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    posting_version: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)

    partner = relationship("Partner", back_populates="documents")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    destination_warehouse = relationship("Warehouse", foreign_keys=[destination_warehouse_id])
    lines = relationship("DocumentLine", back_populates="document", cascade="all, delete-orphan")
    revisions = relationship(
        "DocumentRevision",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentRevision.version",
    )

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
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_document_lines_quantity_nonnegative"),
        CheckConstraint("price >= 0", name="ck_document_lines_price_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_document_lines_total_nonnegative"),
        CheckConstraint("foreign_price IS NULL OR foreign_price >= 0", name="ck_document_lines_foreign_price_nonnegative"),
        CheckConstraint(
            "foreign_line_total IS NULL OR foreign_line_total >= 0",
            name="ck_document_lines_foreign_total_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    foreign_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    foreign_line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    document = relationship("Document", back_populates="lines")
    product = relationship("Product", back_populates="document_lines")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def total(self) -> Decimal:
        return self.line_total


class DocumentNumberSequence(Base):
    __tablename__ = "document_number_sequences"
    __table_args__ = (
        CheckConstraint("last_value >= 0", name="ck_document_number_sequences_last_value_nonnegative"),
    )

    document_type: Mapped[str] = mapped_column(String(60), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DocumentRevision(TimestampMixin, Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_revisions_document_version"),
        CheckConstraint("version > 0", name="ck_document_revisions_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    document = relationship("Document", back_populates="revisions")
    actor = relationship("User")

    @property
    def actor_name(self) -> str | None:
        if self.actor is None:
            return None
        return self.actor.full_name or self.actor.username
