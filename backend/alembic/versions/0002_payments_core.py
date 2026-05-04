"""payments core fields

Revision ID: 0002_payments_core
Revises: 0001_initial
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_payments_core"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("payment_type", sa.String(60), nullable=False, server_default="customer_payment"))
    op.add_column("payments", sa.Column("status", sa.String(40), nullable=False, server_default="draft"))
    op.add_column("cash_operations", sa.Column("status", sa.String(40), nullable=False, server_default="posted"))
    op.add_column("cash_operations", sa.Column("payment_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_cash_operations_payment_id_payments", "cash_operations", "payments", ["payment_id"], ["id"])
    op.create_index("ix_payments_payment_type", "payments", ["payment_type"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_cash_operations_status", "cash_operations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cash_operations_status", table_name="cash_operations")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_payment_type", table_name="payments")
    op.drop_constraint("fk_cash_operations_payment_id_payments", "cash_operations", type_="foreignkey")
    op.drop_column("cash_operations", "payment_id")
    op.drop_column("cash_operations", "status")
    op.drop_column("payments", "status")
    op.drop_column("payments", "payment_type")
