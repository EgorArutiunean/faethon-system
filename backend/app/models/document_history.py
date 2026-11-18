from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DocumentHistory(Base):
    """Immutable legacy snapshots, deliberately outside operational documents."""

    __tablename__ = "document_history"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", name="uq_document_history_source"),
        Index("ix_document_history_date_id", "document_date", "id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80))
    source_key: Mapped[str] = mapped_column(String(120))
    source_database_sha256: Mapped[str] = mapped_column(String(64))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    document_date: Mapped[date] = mapped_column(Date)
    document_type: Mapped[str] = mapped_column(String(16))
    number: Mapped[str] = mapped_column(String(80))
    warehouse_code: Mapped[str] = mapped_column(String(40))
    partner_name: Mapped[str] = mapped_column(String(300))
    partner_code: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
