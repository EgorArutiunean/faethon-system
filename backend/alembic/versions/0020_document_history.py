"""Read-only legacy invoice archive, no operational foreign keys or triggers."""

import sqlalchemy as sa

from alembic import op

revision = "0020_document_history"
down_revision = "0019_opening_inventory"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_system", sa.String(80), nullable=False),
        sa.Column("source_key", sa.String(120), nullable=False),
        sa.Column("source_database_sha256", sa.String(64), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("document_type", sa.String(16), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("warehouse_code", sa.String(40), nullable=False),
        sa.Column("partner_name", sa.String(300), nullable=False),
        sa.Column("partner_code", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_system", "source_key", name="uq_document_history_source"),
    )
    op.create_index("ix_document_history_date_id", "document_history", ["document_date", "id"])


def downgrade():
    op.drop_table("document_history")
