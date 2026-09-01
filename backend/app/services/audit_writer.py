import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.accounting import AuditLog


def change_details(old: dict[str, Any], new: dict[str, Any]) -> str:
    return json.dumps(
        {"old": old, "new": new},
        default=str,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def write_audit(
    db: Session,
    entity_type: str,
    entity_id: int | str,
    action: str,
    details: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=db.info.get("actor_user_id"),
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            details=details,
        )
    )
