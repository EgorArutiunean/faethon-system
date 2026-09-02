"""allow the manager to operate the single cash register

Revision ID: 0013_manager_cash_permissions
Revises: 0012_warehouse_tasks
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_manager_cash_permissions"
down_revision = "0012_warehouse_tasks"
branch_labels = None
depends_on = None


CASH_PERMISSIONS = ("cash.read", "cash.create", "cash.cancel")


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    roles = sa.Table("roles", metadata, autoload_with=bind)
    role_permissions = sa.Table("role_permissions", metadata, autoload_with=bind)

    manager_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == "manager"))
    if manager_id is None:
        return

    for code in CASH_PERMISSIONS:
        permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.code == code))
        if permission_id is None:
            permission_id = bind.execute(
                permissions.insert().values(code=code, description=code).returning(permissions.c.id)
            ).scalar_one()
        exists = bind.scalar(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == manager_id,
                role_permissions.c.permission_id == permission_id,
            )
        )
        if exists is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=manager_id,
                    permission_id=permission_id,
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    roles = sa.Table("roles", metadata, autoload_with=bind)
    role_permissions = sa.Table("role_permissions", metadata, autoload_with=bind)

    manager_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == "manager"))
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.code.in_(CASH_PERMISSIONS)))
    )
    if manager_id is not None and permission_ids:
        bind.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == manager_id,
                role_permissions.c.permission_id.in_(permission_ids),
            )
        )
