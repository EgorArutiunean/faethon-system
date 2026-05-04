"""partner type

Revision ID: 0004_partner_type
Revises: 0003_cash_core
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_partner_type"
down_revision = "0003_cash_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("partner_type", sa.String(40), nullable=False, server_default="both"))
    op.create_index("ix_partners_partner_type", "partners", ["partner_type"])


def downgrade() -> None:
    op.drop_index("ix_partners_partner_type", table_name="partners")
    op.drop_column("partners", "partner_type")
