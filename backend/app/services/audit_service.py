from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_logs = AuditRepository(db)

    def record(
        self,
        event_type: str,
        actor_email: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: str | None = None,
    ) -> None:
        self.audit_logs.create(
            AuditLog(
                event_type=event_type,
                actor_email=actor_email,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
            )
        )
