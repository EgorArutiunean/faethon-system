from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.audit import AuditLogRead
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogRead], dependencies=[Depends(require_permission("audit.read"))])
def list_audit_logs(
    db: Session = Depends(get_db),
    entity_type: str | None = None,
    action: str | None = None,
    entity_id: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
):
    return audit_service.list_audit_logs(
        db,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
    )
