from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Partner(TimestampMixin, Base):
    __tablename__ = "partners"
    __table_args__ = (
        Index("ix_partners_type_name_id", "partner_type", "name", "id"),
        Index(
            "ix_partners_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_partners_code_trgm",
            "code",
            postgresql_using="gin",
            postgresql_ops={"code": "gin_trgm_ops"},
        ),
        Index(
            "ix_partners_phone_trgm",
            "phone",
            postgresql_using="gin",
            postgresql_ops={"phone": "gin_trgm_ops"},
        ),
    )

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
