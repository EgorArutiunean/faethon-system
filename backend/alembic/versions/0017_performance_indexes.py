"""add query-plan-driven performance indexes

Revision ID: 0017_performance_indexes
Revises: 0016_token_revocation
Create Date: 2026-10-11
"""

from alembic import op

revision = "0017_performance_indexes"
down_revision = "0016_token_revocation"
branch_labels = None
depends_on = None


BTREE_INDEXES = (
    ("ix_products_name", "products", ["name"]),
    ("ix_document_lines_document_id", "document_lines", ["document_id"]),
    ("ix_document_lines_product_id", "document_lines", ["product_id"]),
    ("ix_documents_document_date", "documents", ["document_date"]),
    ("ix_documents_document_type", "documents", ["document_type"]),
    ("ix_documents_status", "documents", ["status"]),
    ("ix_documents_partner_id", "documents", ["partner_id"]),
    ("ix_partners_name", "partners", ["name"]),
    ("ix_payments_document_id", "payments", ["document_id"]),
    ("ix_payments_partner_id", "payments", ["partner_id"]),
    ("ix_payments_payment_date", "payments", ["payment_date"]),
    ("ix_cash_operations_direction", "cash_operations", ["direction"]),
    ("ix_cash_operations_operation_date", "cash_operations", ["operation_date"]),
    ("ix_prices_product_id", "prices", ["product_id"]),
    ("ix_stock_balances_product_id", "stock_balances", ["product_id"]),
    ("ix_stock_balances_warehouse_id", "stock_balances", ["warehouse_id"]),
    ("ix_stock_movements_document_id", "stock_movements", ["document_id"]),
    ("ix_stock_movements_product_id", "stock_movements", ["product_id"]),
    ("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"]),
)

COMPOSITE_INDEXES = (
    ("ix_products_group_name_id", "products", ["group_id", "name", "id"]),
    ("ix_partners_type_name_id", "partners", ["partner_type", "name", "id"]),
    (
        "ix_documents_type_status_date_id",
        "documents",
        ["document_type", "status", "document_date", "id"],
    ),
    ("ix_documents_date_id", "documents", ["document_date", "id"]),
    ("ix_cash_operations_date_id", "cash_operations", ["operation_date", "id"]),
)

TRIGRAM_INDEXES = (
    ("ix_products_name_trgm", "products", "name"),
    ("ix_products_sku_trgm", "products", "sku"),
    ("ix_partners_name_trgm", "partners", "name"),
    ("ix_partners_code_trgm", "partners", "code"),
    ("ix_partners_phone_trgm", "partners", "phone"),
    ("ix_documents_number_trgm", "documents", "number"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, columns in BTREE_INDEXES:
        # Some early demo installations were initialized with ORM create_all(),
        # so model-declared indexes may predate the Alembic revision.
        op.create_index(name, table, columns, if_not_exists=True)
    for name, table, columns in COMPOSITE_INDEXES:
        op.create_index(name, table, columns, if_not_exists=True)
    for name, table, column in TRIGRAM_INDEXES:
        op.create_index(
            name,
            table,
            [column],
            if_not_exists=True,
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
        )


def downgrade() -> None:
    for name, table, _column in reversed(TRIGRAM_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
    for name, table, _columns in reversed(COMPOSITE_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
    for name, table, _columns in reversed(BTREE_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
