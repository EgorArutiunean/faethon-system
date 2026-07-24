"""logistics warehouse access

Revision ID: 0008_logistics_access
Revises: 0007_multicurrency
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_logistics_access"
down_revision = "0007_multicurrency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_warehouses",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("user_warehouses")
