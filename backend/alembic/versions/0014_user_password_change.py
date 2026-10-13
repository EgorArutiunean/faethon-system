"""require temporary passwords to be changed

Revision ID: 0014_user_password_change
Revises: 0013_manager_cash_permissions
Create Date: 2026-10-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0014_user_password_change"
down_revision = "0013_manager_cash_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
