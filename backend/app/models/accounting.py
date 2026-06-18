from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Currency(TimestampMixin, Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    symbol: Mapped[str | None] = mapped_column(String(12))
    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExchangeRate(TimestampMixin, Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"), index=True)
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    rate_to_base: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    note: Mapped[str | None] = mapped_column(Text)

    currency = relationship("Currency")

    @property
    def currency_code(self) -> str | None:
        return self.currency.code if self.currency else None


class Price(TimestampMixin, Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    currency_id: Mapped[int | None] = mapped_column(ForeignKey("currencies.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valid_from: Mapped[date | None] = mapped_column(Date)

    product = relationship("Product")
    currency = relationship("Currency")


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CANCELLED = "cancelled"

    TYPE_CUSTOMER_PAYMENT = "customer_payment"
    TYPE_SUPPLIER_PAYMENT = "supplier_payment"
    TYPE_REFUND = "refund"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    payment_type: Mapped[str] = mapped_column(String(60), default=TYPE_CUSTOMER_PAYMENT, index=True)
    status: Mapped[str] = mapped_column(String(40), default=STATUS_DRAFT, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)

    partner = relationship("Partner")
    document = relationship("Document")
    cash_operations = relationship("CashOperation", back_populates="payment")

    @property
    def partner_name(self) -> str | None:
        return self.partner.name if self.partner else None

    @property
    def document_number(self) -> str | None:
        return self.document.number if self.document else None

    @property
    def cash_operation_id(self) -> int | None:
        posted_operation = next((operation for operation in self.cash_operations if operation.status == CashOperation.STATUS_POSTED), None)
        operation = posted_operation or next(iter(self.cash_operations), None)
        return operation.id if operation else None

    @property
    def cash_operation_status(self) -> str | None:
        posted_operation = next((operation for operation in self.cash_operations if operation.status == CashOperation.STATUS_POSTED), None)
        operation = posted_operation or next(iter(self.cash_operations), None)
        return operation.status if operation else None


class CashOperation(TimestampMixin, Base):
    __tablename__ = "cash_operations"

    TYPE_CASH_IN = "cash_in"
    TYPE_CASH_OUT = "cash_out"
    TYPE_CORRECTION = "correction"

    STATUS_POSTED = "posted"
    STATUS_CANCELLED = "cancelled"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_date: Mapped[date] = mapped_column(Date, index=True)
    operation_type: Mapped[str] = mapped_column(String(40), default=TYPE_CASH_IN, index=True)
    direction: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(40), default=STATUS_POSTED, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)

    partner = relationship("Partner")
    document = relationship("Document")
    payment = relationship("Payment", back_populates="cash_operations")
    created_by = relationship("User")

    @property
    def partner_name(self) -> str | None:
        return self.partner.name if self.partner else None

    @property
    def payment_status(self) -> str | None:
        return self.payment.status if self.payment else None


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[str | None] = mapped_column(Text)

    actor = relationship("User")
