from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Partner(TimestampMixin, Base):
    __tablename__ = "partners"

    TYPE_CUSTOMER = "customer"
    TYPE_SUPPLIER = "supplier"
    TYPE_BOTH = "both"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    partner_type: Mapped[str] = mapped_column(String(40), default=TYPE_BOTH, index=True)
    code: Mapped[str | None] = mapped_column(String(80), unique=True)
    tax_id: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    documents = relationship("Document", back_populates="partner")
