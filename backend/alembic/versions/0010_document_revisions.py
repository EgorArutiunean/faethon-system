"""version posted documents and stock movements

Revision ID: 0010_document_revisions
Revises: 0009_integrity_guards
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_document_revisions"
down_revision = "0009_integrity_guards"
branch_labels = None
depends_on = None


def _snapshot(document, lines, products) -> dict:
    return {
        "document_type": document.document_type,
        "number": document.number,
        "document_date": str(document.document_date),
        "status": "posted",
        "partner_id": document.partner_id,
        "warehouse_id": document.warehouse_id,
        "destination_warehouse_id": document.destination_warehouse_id,
        "total_amount": str(document.total_amount),
        "currency_code": document.currency_code,
        "exchange_rate": str(document.exchange_rate),
        "foreign_total_amount": str(document.foreign_total_amount),
        "note": document.note,
        "lines": [
            {
                "product_id": line.product_id,
                "product_name": products.get(line.product_id, {}).get("name"),
                "product_sku": products.get(line.product_id, {}).get("sku"),
                "quantity": str(line.quantity),
                "price": str(line.price),
                "line_total": str(line.line_total),
                "foreign_price": str(line.foreign_price) if line.foreign_price is not None else None,
                "foreign_line_total": (
                    str(line.foreign_line_total) if line.foreign_line_total is not None else None
                ),
            }
            for line in lines
        ],
    }


def _backfill_revisions() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=bind)
    lines = sa.Table("document_lines", metadata, autoload_with=bind)
    product_table = sa.Table("products", metadata, autoload_with=bind)
    revisions = sa.Table("document_revisions", metadata, autoload_with=bind)
    products = {
        row.id: {"name": row.name, "sku": row.sku}
        for row in bind.execute(sa.select(product_table)).mappings()
    }
    rows = list(bind.execute(
        sa.select(documents).where(documents.c.status.in_(["posted", "cancelled"]))
    ).mappings())
    for document in rows:
        document_lines = list(
            bind.execute(
                sa.select(lines).where(lines.c.document_id == document.id).order_by(lines.c.id)
            ).mappings()
        )
        bind.execute(
            revisions.insert().values(
                document_id=document.id,
                version=1,
                reason="Перенесённая проведённая версия",
                actor_user_id=None,
                snapshot=_snapshot(document, document_lines, products),
            )
        )


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_documents_posting_version_nonnegative",
        "documents",
        "posting_version >= 0",
    )
    op.execute("UPDATE documents SET posting_version = 1 WHERE status IN ('posted', 'cancelled')")

    op.add_column("stock_movements", sa.Column("posting_version", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("movement_kind", sa.String(20), nullable=True))
    op.create_index("ix_stock_movements_posting_version", "stock_movements", ["posting_version"])
    op.create_index("ix_stock_movements_movement_kind", "stock_movements", ["movement_kind"])
    op.create_check_constraint(
        "ck_stock_movements_posting_version_positive",
        "stock_movements",
        "posting_version IS NULL OR posting_version > 0",
    )
    op.create_check_constraint(
        "ck_stock_movements_kind",
        "stock_movements",
        "movement_kind IS NULL OR movement_kind IN ('apply', 'reverse')",
    )
    op.execute(
        "UPDATE stock_movements SET posting_version = 1, movement_kind = 'apply' "
        "WHERE document_id IS NOT NULL AND reason LIKE 'post:%'"
    )
    op.execute(
        "UPDATE stock_movements SET posting_version = 1, movement_kind = 'reverse' "
        "WHERE document_id IS NOT NULL AND reason LIKE 'cancel:%'"
    )

    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "version", name="uq_document_revisions_document_version"),
        sa.CheckConstraint("version > 0", name="ck_document_revisions_version_positive"),
    )
    op.create_index("ix_document_revisions_document_id", "document_revisions", ["document_id"])
    _backfill_revisions()


def downgrade() -> None:
    op.drop_index("ix_document_revisions_document_id", table_name="document_revisions")
    op.drop_table("document_revisions")
    op.drop_constraint("ck_stock_movements_kind", "stock_movements", type_="check")
    op.drop_constraint("ck_stock_movements_posting_version_positive", "stock_movements", type_="check")
    op.drop_index("ix_stock_movements_movement_kind", table_name="stock_movements")
    op.drop_index("ix_stock_movements_posting_version", table_name="stock_movements")
    op.drop_column("stock_movements", "movement_kind")
    op.drop_column("stock_movements", "posting_version")
    op.drop_constraint("ck_documents_posting_version_nonnegative", "documents", type_="check")
    op.drop_column("documents", "posting_version")
