"""payment draft permissions

Revision ID: 0006_payment_draft_permissions
Revises: 0005_transfer_documents
Create Date: 2026-06-17
"""

from alembic import op

revision = "0006_payment_draft_permissions"
down_revision = "0005_transfer_documents"
branch_labels = None
depends_on = None


PERMISSIONS = ("payments.update", "payments.delete")
ROLES = ("admin", "cashier")


def upgrade() -> None:
    for code in PERMISSIONS:
        op.execute(
            f"""
            INSERT INTO permissions (code, description)
            SELECT '{code}', '{code}'
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE code = '{code}'
            )
            """
        )
        for role in ROLES:
            op.execute(
                f"""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT roles.id, permissions.id
                FROM roles, permissions
                WHERE roles.name = '{role}'
                  AND permissions.code = '{code}'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM role_permissions
                      WHERE role_permissions.role_id = roles.id
                        AND role_permissions.permission_id = permissions.id
                  )
                """
            )


def downgrade() -> None:
    for code in PERMISSIONS:
        op.execute(
            f"""
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code = '{code}'
            )
            """
        )
        op.execute(f"DELETE FROM permissions WHERE code = '{code}'")
