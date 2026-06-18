"""multicurrency incoming documents

Revision ID: 0007_multicurrency
Revises: 0006_payment_draft_permissions
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_multicurrency"
down_revision = "0006_payment_draft_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("currencies", "code", type_=sa.String(12), existing_type=sa.String(3))
    op.add_column("currencies", sa.Column("symbol", sa.String(12), nullable=True))
    op.add_column("currencies", sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("currencies", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate_to_base", sa.Numeric(14, 6), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_rates_currency_id", "exchange_rates", ["currency_id"])
    op.create_index("ix_exchange_rates_rate_date", "exchange_rates", ["rate_date"])

    op.add_column("documents", sa.Column("currency_code", sa.String(12), nullable=False, server_default="RUB_PMR"))
    op.add_column("documents", sa.Column("exchange_rate", sa.Numeric(14, 6), nullable=False, server_default="1"))
    op.add_column("documents", sa.Column("foreign_total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("document_lines", sa.Column("foreign_price", sa.Numeric(14, 2), nullable=True))
    op.add_column("document_lines", sa.Column("foreign_line_total", sa.Numeric(14, 2), nullable=True))

    currencies = sa.table(
        "currencies",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("symbol", sa.String),
        sa.column("is_base", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        currencies,
        [
            {"code": "RUB_PMR", "name": "Рубль ПМР", "symbol": "р.", "is_base": True, "is_active": True},
            {"code": "MDL", "name": "Молдавский лей", "symbol": "L", "is_base": False, "is_active": True},
            {"code": "USD", "name": "Доллар США", "symbol": "$", "is_base": False, "is_active": True},
            {"code": "EUR", "name": "Евро", "symbol": "€", "is_base": False, "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_column("document_lines", "foreign_line_total")
    op.drop_column("document_lines", "foreign_price")
    op.drop_column("documents", "foreign_total_amount")
    op.drop_column("documents", "exchange_rate")
    op.drop_column("documents", "currency_code")
    op.drop_index("ix_exchange_rates_rate_date", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_currency_id", table_name="exchange_rates")
    op.drop_table("exchange_rates")
    op.drop_column("currencies", "is_active")
    op.drop_column("currencies", "is_base")
    op.drop_column("currencies", "symbol")
    op.alter_column("currencies", "code", type_=sa.String(3), existing_type=sa.String(12))
