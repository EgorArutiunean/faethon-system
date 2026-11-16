"""Opening inventory values and product cost baseline."""

import sqlalchemy as sa
from alembic import op

revision = "0019_opening_inventory"
down_revision = "0018_reconcile_model_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("opening_unit_cost", sa.Numeric(28, 12), nullable=True))
    op.add_column("products", sa.Column("opening_cost_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_products_opening_cost_nonnegative",
        "products",
        "opening_unit_cost IS NULL OR opening_unit_cost >= 0",
    )
    op.create_table(
        "inventory_openings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_key", sa.String(64), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(28, 12), nullable=False),
        sa.Column("amount", sa.Numeric(28, 12), nullable=False),
        sa.Column("sale_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency_code", sa.String(12), nullable=False),
        sa.Column("source_data", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "batch_key",
            "product_id",
            "warehouse_id",
            name="uq_inventory_opening_batch_product_warehouse",
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND unit_cost >= 0 AND amount >= 0 AND sale_price >= 0",
            name="ck_inventory_opening_nonnegative",
        ),
    )


def downgrade():
    op.drop_table("inventory_openings")
    op.drop_constraint("ck_products_opening_cost_nonnegative", "products", type_="check")
    op.drop_column("products", "opening_cost_date")
    op.drop_column("products", "opening_unit_cost")
