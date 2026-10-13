"""reconcile ORM metadata with the migrated schema

Revision ID: 0018_reconcile_model_schema
Revises: 0017_performance_indexes
Create Date: 2026-10-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_reconcile_model_schema"
down_revision = "0017_performance_indexes"
branch_labels = None
depends_on = None


TIMESTAMP_TABLES = (
    "audit_log",
    "cash_operations",
    "currencies",
    "document_lines",
    "documents",
    "exchange_rates",
    "partners",
    "payments",
    "permissions",
    "prices",
    "product_groups",
    "products",
    "roles",
    "stock_balances",
    "stock_movements",
    "units",
    "users",
    "warehouses",
)

NON_NULL_DEFAULTS = (
    ("document_lines", "line_total", "0", sa.Numeric(14, 2)),
    ("documents", "total_amount", "0", sa.Numeric(14, 2)),
    ("partners", "is_active", "true", sa.Boolean()),
    ("products", "is_active", "true", sa.Boolean()),
    ("stock_balances", "quantity", "0", sa.Numeric(14, 3)),
    ("users", "is_active", "true", sa.Boolean()),
)

MISSING_INDEXES = (
    ("ix_audit_log_action", "audit_log", ["action"]),
    ("ix_audit_log_entity_id", "audit_log", ["entity_id"]),
    ("ix_audit_log_entity_type", "audit_log", ["entity_type"]),
    ("ix_documents_number", "documents", ["number"]),
    ("ix_product_groups_name", "product_groups", ["name"]),
    ("ix_warehouses_name", "warehouses", ["name"]),
)


def upgrade() -> None:
    # Historical migrations allowed nulls even though ORM annotations have always
    # treated these fields as required. Backfill first so existing installations
    # can adopt the constraint safely.
    for table in TIMESTAMP_TABLES:
        op.execute(
            sa.text(f'UPDATE "{table}" SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
        )
        op.execute(
            sa.text(
                f'UPDATE "{table}" SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) '
                "WHERE updated_at IS NULL"
            )
        )
        op.alter_column(
            table, "created_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
        op.alter_column(
            table, "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )

    for table, column, sql_default, column_type in NON_NULL_DEFAULTS:
        op.execute(
            sa.text(f'UPDATE "{table}" SET "{column}" = {sql_default} WHERE "{column}" IS NULL')
        )
        op.alter_column(table, column, existing_type=column_type, nullable=False)

    for name, table, columns in MISSING_INDEXES:
        # Legacy/demo databases may already contain indexes created directly
        # from ORM metadata. Adopting such a database must remain repeatable.
        op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, _columns in reversed(MISSING_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)

    for table, column, _sql_default, column_type in reversed(NON_NULL_DEFAULTS):
        op.alter_column(table, column, existing_type=column_type, nullable=True)

    for table in reversed(TIMESTAMP_TABLES):
        op.alter_column(
            table, "updated_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )
        op.alter_column(
            table, "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )
