"""transfer documents

Revision ID: 0005_transfer_documents
Revises: 0004_partner_type
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_transfer_documents"
down_revision = "0004_partner_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("destination_warehouse_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_documents_destination_warehouse_id_warehouses",
        "documents",
        "warehouses",
        ["destination_warehouse_id"],
        ["id"],
    )
    op.create_index("ix_documents_destination_warehouse_id", "documents", ["destination_warehouse_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_destination_warehouse_id", table_name="documents")
    op.drop_constraint("fk_documents_destination_warehouse_id_warehouses", "documents", type_="foreignkey")
    op.drop_column("documents", "destination_warehouse_id")
