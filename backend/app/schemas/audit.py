from app.schemas.common import Timestamped


class AuditLogRead(Timestamped):
    id: int
    actor_user_id: int | None = None
    entity_type: str
    entity_id: str
    action: str
    details: str | None = None
