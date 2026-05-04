"""cash core fields

Revision ID: 0003_cash_core
Revises: 0002_payments_core
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_cash_core"
down_revision = "0002_payments_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cash_operations", sa.Column("operation_type", sa.String(40), nullable=False, server_default="cash_in"))
    op.add_column("cash_operations", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_cash_operations_created_by_id_users", "cash_operations", "users", ["created_by_id"], ["id"])
    op.create_index("ix_cash_operations_operation_type", "cash_operations", ["operation_type"])


def downgrade() -> None:
    op.drop_index("ix_cash_operations_operation_type", table_name="cash_operations")
    op.drop_constraint("fk_cash_operations_created_by_id_users", "cash_operations", type_="foreignkey")
    op.drop_column("cash_operations", "created_by_id")
    op.drop_column("cash_operations", "operation_type")
