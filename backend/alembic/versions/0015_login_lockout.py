"""add persistent login lockout state

Revision ID: 0015_login_lockout
Revises: 0014_user_password_change
Create Date: 2026-10-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_login_lockout"
down_revision = "0014_user_password_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
