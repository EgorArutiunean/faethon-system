from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import AuditLog


def list_audit_logs(
    db: Session,
    *,
    entity_type: str | None = None,
    action: str | None = None,
    entity_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    return list(db.scalars(stmt.offset(skip).limit(limit)).all())
