from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class WarehouseTask(TimestampMixin, Base):
    __tablename__ = "warehouse_tasks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "posting_version",
            "warehouse_id",
            "task_type",
            name="uq_warehouse_tasks_document_version_warehouse_type",
        ),
        CheckConstraint("posting_version > 0", name="ck_warehouse_tasks_posting_version_positive"),
        CheckConstraint(
            "task_type IN ('incoming_receive', 'outgoing_dispatch', 'transfer_dispatch', 'transfer_receive')",
            name="ck_warehouse_tasks_type",
        ),
        CheckConstraint(
            "status IN ('blocked', 'pending', 'in_transit', 'in_progress', 'needs_review', 'completed', 'cancelled')",
            name="ck_warehouse_tasks_status",
        ),
    )

    TYPE_INCOMING_RECEIVE = "incoming_receive"
    TYPE_OUTGOING_DISPATCH = "outgoing_dispatch"
    TYPE_TRANSFER_DISPATCH = "transfer_dispatch"
    TYPE_TRANSFER_RECEIVE = "transfer_receive"

    STATUS_BLOCKED = "blocked"
    STATUS_PENDING = "pending"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    posting_version: Mapped[int] = mapped_column(Integer, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default=STATUS_PENDING)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document = relationship("Document")
    warehouse = relationship("Warehouse")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    lines = relationship(
        "WarehouseTaskLine",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="WarehouseTaskLine.id",
    )
    events = relationship(
        "WarehouseTaskEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="WarehouseTaskEvent.id",
    )

    @property
    def document_number(self) -> str | None:
        return self.document.number if self.document else None

    @property
    def document_date(self):
        return self.document.document_date if self.document else None

    @property
    def document_type(self) -> str | None:
        return self.document.document_type if self.document else None

    @property
    def partner_name(self) -> str | None:
        return self.document.partner_name if self.document else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None

    @property
    def assigned_to_name(self) -> str | None:
        if self.assigned_to is None:
            return None
        return self.assigned_to.full_name or self.assigned_to.username


class WarehouseTaskLine(TimestampMixin, Base):
    __tablename__ = "warehouse_task_lines"
    __table_args__ = (
        CheckConstraint("expected_quantity >= 0", name="ck_warehouse_task_lines_expected_nonnegative"),
        CheckConstraint(
            "actual_quantity IS NULL OR actual_quantity >= 0",
            name="ck_warehouse_task_lines_actual_nonnegative",
        ),
        CheckConstraint("sale_price >= 0", name="ck_warehouse_task_lines_sale_price_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'discrepancy')",
            name="ck_warehouse_task_lines_status",
        ),
    )

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DISCREPANCY = "discrepancy"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("warehouse_tasks.id", ondelete="CASCADE"), index=True)
    document_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_lines.id", ondelete="SET NULL"),
        index=True,
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    expected_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    sale_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING, index=True)
    comment: Mapped[str | None] = mapped_column(Text)

    task = relationship("WarehouseTask", back_populates="lines")
    document_line = relationship("DocumentLine")
    product = relationship("Product")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None


class WarehouseTaskEvent(TimestampMixin, Base):
    __tablename__ = "warehouse_task_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("warehouse_tasks.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)

    task = relationship("WarehouseTask", back_populates="events")
    actor = relationship("User")

    @property
    def actor_name(self) -> str | None:
        if self.actor is None:
            return None
        return self.actor.full_name or self.actor.username
