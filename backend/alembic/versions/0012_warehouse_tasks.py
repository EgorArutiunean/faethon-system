"""warehouse execution tasks

Revision ID: 0012_warehouse_tasks
Revises: 0011_payment_allocations
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_warehouse_tasks"
down_revision = "0011_payment_allocations"
branch_labels = None
depends_on = None


def _task_specs(document) -> list[tuple[int, str, str]]:
    if document.document_type == "incoming" and document.warehouse_id is not None:
        return [(document.warehouse_id, "incoming_receive", "pending")]
    if document.document_type == "outgoing" and document.warehouse_id is not None:
        return [(document.warehouse_id, "outgoing_dispatch", "pending")]
    if (
        document.document_type == "transfer"
        and document.warehouse_id is not None
        and document.destination_warehouse_id is not None
    ):
        return [
            (document.warehouse_id, "transfer_dispatch", "pending"),
            (document.destination_warehouse_id, "transfer_receive", "blocked"),
        ]
    return []


def _backfill_tasks() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=bind)
    document_lines = sa.Table("document_lines", metadata, autoload_with=bind)
    products = sa.Table("products", metadata, autoload_with=bind)
    tasks = sa.Table("warehouse_tasks", metadata, autoload_with=bind)
    task_lines = sa.Table("warehouse_task_lines", metadata, autoload_with=bind)
    events = sa.Table("warehouse_task_events", metadata, autoload_with=bind)

    document_rows = bind.execute(
        sa.select(documents)
        .where(
            documents.c.status == "posted",
            documents.c.posting_version > 0,
            documents.c.document_type.in_(["incoming", "outgoing", "transfer"]),
        )
        .order_by(documents.c.id)
    ).mappings()
    for document in document_rows:
        lines = list(
            bind.execute(
                sa.select(document_lines)
                .where(document_lines.c.document_id == document.id)
                .order_by(document_lines.c.id)
            ).mappings()
        )
        for warehouse_id, task_type, status in _task_specs(document):
            task_id = bind.execute(
                tasks.insert()
                .values(
                    document_id=document.id,
                    posting_version=document.posting_version,
                    warehouse_id=warehouse_id,
                    task_type=task_type,
                    status=status,
                )
                .returning(tasks.c.id)
            ).scalar_one()
            if lines:
                bind.execute(
                    task_lines.insert(),
                    [
                        {
                            "task_id": task_id,
                            "document_line_id": line.id,
                            "product_id": line.product_id,
                            "expected_quantity": line.quantity,
                            "sale_price": (
                                line.price
                                if document.document_type == "outgoing"
                                else bind.execute(
                                    sa.select(products.c.base_price).where(products.c.id == line.product_id)
                                ).scalar()
                                or 0
                            ),
                            "status": "pending",
                        }
                        for line in lines
                    ],
                )
            bind.execute(
                events.insert().values(
                    task_id=task_id,
                    event_type="generated",
                    to_status=status,
                    note="Создано для ранее проведённого документа",
                )
            )


def _seed_logistics_permissions() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    roles = sa.Table("roles", metadata, autoload_with=bind)
    role_permissions = sa.Table("role_permissions", metadata, autoload_with=bind)

    permission_ids: dict[str, int] = {}
    for code in ("logistics.read", "logistics.process", "logistics.review"):
        permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.code == code))
        if permission_id is None:
            result = bind.execute(
                permissions.insert()
                .values(code=code, description=code)
                .returning(permissions.c.id)
            )
            permission_id = result.scalar_one()
        permission_ids[code] = permission_id

    role_codes = {
        "admin": ("logistics.read", "logistics.process", "logistics.review"),
        "manager": ("logistics.read", "logistics.process", "logistics.review"),
        "logist": ("logistics.read", "logistics.process"),
    }
    for role_name, codes in role_codes.items():
        role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == role_name))
        if role_id is None:
            continue
        for code in codes:
            permission_id = permission_ids[code]
            exists = bind.scalar(
                sa.select(role_permissions.c.role_id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            )
            if exists is None:
                bind.execute(
                    role_permissions.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def _remove_logistics_permissions() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    roles = sa.Table("roles", metadata, autoload_with=bind)
    role_permissions = sa.Table("role_permissions", metadata, autoload_with=bind)
    removals = {
        "admin": ("logistics.process", "logistics.review"),
        "manager": ("logistics.read", "logistics.process", "logistics.review"),
        "logist": ("logistics.process",),
    }
    for role_name, codes in removals.items():
        role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == role_name))
        permission_ids = list(
            bind.scalars(sa.select(permissions.c.id).where(permissions.c.code.in_(codes)))
        )
        if role_id is not None and permission_ids:
            bind.execute(
                role_permissions.delete().where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id.in_(permission_ids),
                )
            )
    removable_ids = list(
        bind.scalars(
            sa.select(permissions.c.id).where(
                permissions.c.code.in_(("logistics.process", "logistics.review"))
            )
        )
    )
    if removable_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(removable_ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(removable_ids)))


def upgrade() -> None:
    op.create_table(
        "warehouse_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("posting_version", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "posting_version",
            "warehouse_id",
            "task_type",
            name="uq_warehouse_tasks_document_version_warehouse_type",
        ),
        sa.CheckConstraint("posting_version > 0", name="ck_warehouse_tasks_posting_version_positive"),
        sa.CheckConstraint(
            "task_type IN ('incoming_receive', 'outgoing_dispatch', 'transfer_dispatch', 'transfer_receive')",
            name="ck_warehouse_tasks_type",
        ),
        sa.CheckConstraint(
            "status IN ('blocked', 'pending', 'in_transit', 'in_progress', 'needs_review', 'completed', 'cancelled')",
            name="ck_warehouse_tasks_status",
        ),
    )
    op.create_index("ix_warehouse_tasks_document_id", "warehouse_tasks", ["document_id"])
    op.create_index("ix_warehouse_tasks_posting_version", "warehouse_tasks", ["posting_version"])
    op.create_index("ix_warehouse_tasks_warehouse_id", "warehouse_tasks", ["warehouse_id"])
    op.create_index("ix_warehouse_tasks_task_type", "warehouse_tasks", ["task_type"])
    op.create_index("ix_warehouse_tasks_status", "warehouse_tasks", ["status"])
    op.create_index("ix_warehouse_tasks_assigned_to_id", "warehouse_tasks", ["assigned_to_id"])

    op.create_table(
        "warehouse_task_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("warehouse_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "document_line_id",
            sa.Integer(),
            sa.ForeignKey("document_lines.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("sale_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("expected_quantity >= 0", name="ck_warehouse_task_lines_expected_nonnegative"),
        sa.CheckConstraint(
            "actual_quantity IS NULL OR actual_quantity >= 0",
            name="ck_warehouse_task_lines_actual_nonnegative",
        ),
        sa.CheckConstraint("sale_price >= 0", name="ck_warehouse_task_lines_sale_price_nonnegative"),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'discrepancy')",
            name="ck_warehouse_task_lines_status",
        ),
    )
    op.create_index("ix_warehouse_task_lines_task_id", "warehouse_task_lines", ["task_id"])
    op.create_index("ix_warehouse_task_lines_document_line_id", "warehouse_task_lines", ["document_line_id"])
    op.create_index("ix_warehouse_task_lines_product_id", "warehouse_task_lines", ["product_id"])
    op.create_index("ix_warehouse_task_lines_status", "warehouse_task_lines", ["status"])

    op.create_table(
        "warehouse_task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("warehouse_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_warehouse_task_events_task_id", "warehouse_task_events", ["task_id"])
    op.create_index("ix_warehouse_task_events_actor_user_id", "warehouse_task_events", ["actor_user_id"])
    op.create_index("ix_warehouse_task_events_event_type", "warehouse_task_events", ["event_type"])
    _seed_logistics_permissions()
    _backfill_tasks()


def downgrade() -> None:
    _remove_logistics_permissions()
    op.drop_index("ix_warehouse_task_events_event_type", table_name="warehouse_task_events")
    op.drop_index("ix_warehouse_task_events_actor_user_id", table_name="warehouse_task_events")
    op.drop_index("ix_warehouse_task_events_task_id", table_name="warehouse_task_events")
    op.drop_table("warehouse_task_events")
    op.drop_index("ix_warehouse_task_lines_status", table_name="warehouse_task_lines")
    op.drop_index("ix_warehouse_task_lines_product_id", table_name="warehouse_task_lines")
    op.drop_index("ix_warehouse_task_lines_document_line_id", table_name="warehouse_task_lines")
    op.drop_index("ix_warehouse_task_lines_task_id", table_name="warehouse_task_lines")
    op.drop_table("warehouse_task_lines")
    op.drop_index("ix_warehouse_tasks_assigned_to_id", table_name="warehouse_tasks")
    op.drop_index("ix_warehouse_tasks_status", table_name="warehouse_tasks")
    op.drop_index("ix_warehouse_tasks_task_type", table_name="warehouse_tasks")
    op.drop_index("ix_warehouse_tasks_warehouse_id", table_name="warehouse_tasks")
    op.drop_index("ix_warehouse_tasks_posting_version", table_name="warehouse_tasks")
    op.drop_index("ix_warehouse_tasks_document_id", table_name="warehouse_tasks")
    op.drop_table("warehouse_tasks")
