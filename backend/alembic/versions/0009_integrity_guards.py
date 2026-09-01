"""integrity guards and document number sequences

Revision ID: 0009_integrity_guards
Revises: 0008_logistics_access
Create Date: 2026-09-01
"""

from collections import defaultdict

from alembic import op
import sqlalchemy as sa


revision = "0009_integrity_guards"
down_revision = "0008_logistics_access"
branch_labels = None
depends_on = None


PREFIXES = {
    "incoming": "IN",
    "outgoing": "OUT",
    "adjustment": "ADJ",
    "transfer": "TR",
}


def _assert_existing_data_is_valid() -> None:
    bind = op.get_bind()
    validations = {
        "documents contain negative totals or invalid exchange rates": """
            SELECT 1 FROM documents
            WHERE total_amount < 0 OR foreign_total_amount < 0 OR exchange_rate <= 0
            LIMIT 1
        """,
        "document lines contain negative values": """
            SELECT 1 FROM document_lines
            WHERE quantity < 0 OR price < 0 OR line_total < 0
               OR foreign_price < 0 OR foreign_line_total < 0
            LIMIT 1
        """,
        "products contain negative sale prices": "SELECT 1 FROM products WHERE base_price < 0 LIMIT 1",
        "prices contain negative values": "SELECT 1 FROM prices WHERE amount < 0 LIMIT 1",
        "payments contain zero or negative values": "SELECT 1 FROM payments WHERE amount <= 0 LIMIT 1",
        "cash operations contain negative values": "SELECT 1 FROM cash_operations WHERE amount < 0 LIMIT 1",
        "exchange rates contain zero or negative values": "SELECT 1 FROM exchange_rates WHERE rate_to_base <= 0 LIMIT 1",
        "stock balances contain negative values": "SELECT 1 FROM stock_balances WHERE quantity < 0 LIMIT 1",
        "document numbers are duplicated": """
            SELECT 1 FROM documents
            WHERE number IS NOT NULL
            GROUP BY number HAVING COUNT(*) > 1
            LIMIT 1
        """,
    }
    for message, query in validations.items():
        if bind.execute(sa.text(query)).first() is not None:
            raise RuntimeError(f"Cannot apply integrity migration: {message}")


def _seed_document_sequences() -> None:
    bind = op.get_bind()
    maximums: dict[str, int] = defaultdict(int)
    rows = bind.execute(sa.text("SELECT document_type, number FROM documents WHERE number IS NOT NULL"))
    for document_type, number in rows:
        prefix = PREFIXES.get(document_type)
        if not prefix or not number.startswith(f"{prefix}-"):
            continue
        try:
            maximums[document_type] = max(maximums[document_type], int(number.rsplit("-", 1)[1]))
        except ValueError:
            continue
    if maximums:
        sequence_table = sa.table(
            "document_number_sequences",
            sa.column("document_type", sa.String),
            sa.column("last_value", sa.Integer),
        )
        op.bulk_insert(
            sequence_table,
            [
                {"document_type": document_type, "last_value": last_value}
                for document_type, last_value in sorted(maximums.items())
            ],
        )


def upgrade() -> None:
    _assert_existing_data_is_valid()
    op.create_table(
        "document_number_sequences",
        sa.Column("document_type", sa.String(60), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("last_value >= 0", name="ck_document_number_sequences_last_value_nonnegative"),
    )
    _seed_document_sequences()

    op.add_column("cash_operations", sa.Column("target_balance", sa.Numeric(14, 2), nullable=True))
    op.create_unique_constraint("uq_documents_number", "documents", ["number"])
    op.create_check_constraint("ck_documents_total_nonnegative", "documents", "total_amount >= 0")
    op.create_check_constraint("ck_documents_foreign_total_nonnegative", "documents", "foreign_total_amount >= 0")
    op.create_check_constraint("ck_documents_exchange_rate_positive", "documents", "exchange_rate > 0")
    op.create_check_constraint("ck_document_lines_quantity_nonnegative", "document_lines", "quantity >= 0")
    op.create_check_constraint("ck_document_lines_price_nonnegative", "document_lines", "price >= 0")
    op.create_check_constraint("ck_document_lines_total_nonnegative", "document_lines", "line_total >= 0")
    op.create_check_constraint(
        "ck_document_lines_foreign_price_nonnegative",
        "document_lines",
        "foreign_price IS NULL OR foreign_price >= 0",
    )
    op.create_check_constraint(
        "ck_document_lines_foreign_total_nonnegative",
        "document_lines",
        "foreign_line_total IS NULL OR foreign_line_total >= 0",
    )
    op.create_check_constraint("ck_products_base_price_nonnegative", "products", "base_price IS NULL OR base_price >= 0")
    op.create_check_constraint("ck_prices_amount_nonnegative", "prices", "amount >= 0")
    op.create_check_constraint("ck_payments_amount_positive", "payments", "amount > 0")
    op.create_check_constraint("ck_cash_operations_amount_nonnegative", "cash_operations", "amount >= 0")
    op.create_check_constraint(
        "ck_cash_operations_target_balance_nonnegative",
        "cash_operations",
        "target_balance IS NULL OR target_balance >= 0",
    )
    op.create_check_constraint("ck_exchange_rates_rate_positive", "exchange_rates", "rate_to_base > 0")
    op.create_check_constraint("ck_stock_balances_quantity_nonnegative", "stock_balances", "quantity >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_stock_balances_quantity_nonnegative", "stock_balances", type_="check")
    op.drop_constraint("ck_exchange_rates_rate_positive", "exchange_rates", type_="check")
    op.drop_constraint("ck_cash_operations_target_balance_nonnegative", "cash_operations", type_="check")
    op.drop_constraint("ck_cash_operations_amount_nonnegative", "cash_operations", type_="check")
    op.drop_constraint("ck_payments_amount_positive", "payments", type_="check")
    op.drop_constraint("ck_prices_amount_nonnegative", "prices", type_="check")
    op.drop_constraint("ck_products_base_price_nonnegative", "products", type_="check")
    op.drop_constraint("ck_document_lines_foreign_total_nonnegative", "document_lines", type_="check")
    op.drop_constraint("ck_document_lines_foreign_price_nonnegative", "document_lines", type_="check")
    op.drop_constraint("ck_document_lines_total_nonnegative", "document_lines", type_="check")
    op.drop_constraint("ck_document_lines_price_nonnegative", "document_lines", type_="check")
    op.drop_constraint("ck_document_lines_quantity_nonnegative", "document_lines", type_="check")
    op.drop_constraint("ck_documents_exchange_rate_positive", "documents", type_="check")
    op.drop_constraint("ck_documents_foreign_total_nonnegative", "documents", type_="check")
    op.drop_constraint("ck_documents_total_nonnegative", "documents", type_="check")
    op.drop_constraint("uq_documents_number", "documents", type_="unique")
    op.drop_column("cash_operations", "target_balance")
    op.drop_table("document_number_sequences")
