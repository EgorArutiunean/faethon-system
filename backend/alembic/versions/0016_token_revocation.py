"""add token revocation version

Revision ID: 0016_token_revocation
Revises: 0015_login_lockout
Create Date: 2026-10-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_token_revocation"
down_revision = "0015_login_lockout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
