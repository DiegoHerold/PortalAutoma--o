from datetime import datetime
from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    actor: str | None  # actor_email
    actor_type: str | None
    action: str  # event_type
    entity_type: str | None  # resource_type
    entity_id: str | None  # resource_id
    created_at: datetime
    before: dict | None = None
    after: dict | None = None
    message: str | None = None  # details

    model_config = {"from_attributes": True}

    @classmethod
    def from_audit_log(cls, audit_log):
        return cls(
            id=audit_log.id,
            actor=audit_log.actor_email,
            actor_type=audit_log.actor_type or "user",
            action=audit_log.event_type,
            entity_type=audit_log.resource_type,
            entity_id=audit_log.resource_id,
            created_at=audit_log.created_at,
            before=audit_log.before,
            after=audit_log.after,
            message=audit_log.details,
        )
