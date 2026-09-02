"""manual payment allocations

Revision ID: 0011_payment_allocations
Revises: 0010_document_revisions
Create Date: 2026-09-02
"""

from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "0011_payment_allocations"
down_revision = "0010_document_revisions"
branch_labels = None
depends_on = None


def _backfill_allocations() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    payments = sa.Table("payments", metadata, autoload_with=bind)
    documents = sa.Table("documents", metadata, autoload_with=bind)
    allocations = sa.Table("payment_allocations", metadata, autoload_with=bind)
    document_rows = {
        row.id: row
        for row in bind.execute(sa.select(documents)).mappings()
    }
    remaining = {
        document_id: Decimal(str(document.total_amount))
        for document_id, document in document_rows.items()
        if document.status == "posted"
    }
    payment_rows = list(
        bind.execute(
            sa.select(payments)
            .where(payments.c.document_id.is_not(None), payments.c.status != "cancelled")
            .order_by(payments.c.payment_date, payments.c.id)
        ).mappings()
    )
    for payment in payment_rows:
        document = document_rows.get(payment.document_id)
        available = remaining.get(payment.document_id, Decimal("0"))
        if document is None or available <= 0 or document.partner_id != payment.partner_id:
            continue
        amount = min(Decimal(str(payment.amount)), available)
        if amount <= 0:
            continue
        bind.execute(
            allocations.insert().values(
                payment_id=payment.id,
                document_id=payment.document_id,
                amount=amount,
            )
        )
        if payment.status == "posted":
            remaining[payment.document_id] = available - amount


def upgrade() -> None:
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("payment_id", "document_id", name="uq_payment_allocations_payment_document"),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_amount_positive"),
    )
    op.create_index("ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index("ix_payment_allocations_document_id", "payment_allocations", ["document_id"])
    _backfill_allocations()


def downgrade() -> None:
    op.drop_index("ix_payment_allocations_document_id", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_payment_id", table_name="payment_allocations")
    op.drop_table("payment_allocations")
