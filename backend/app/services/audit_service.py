from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.governance.application.use_cases import ListAuditEvents
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.audit_events = SqlAlchemyAuditEventRepository(db)

    def record(
        self,
        action: str,
        actor_email: str | None = None,
        actor_type: str = "user",
        entity_type: str | None = None,
        entity_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        metadata = {"message": details} if details else {}
        self.audit_events.append(
            AuditEvent(
                id=f"aud_{uuid4().hex}",
                actor_type=actor_type,
                actor_id=actor_email,
                action=action,
                resource_type=entity_type or resource_type or "unknown",
                resource_id=entity_id or resource_id or "unknown",
                before=before,
                after=after,
                metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )

    def get_audit_logs(
        self,
        actor: str | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        events = ListAuditEvents(self.audit_events).execute(
            actor=actor,
            resource_type=entity_type,
            action=action,
            limit=limit,
            offset=offset,
        )
        return [
            SimpleNamespace(
                id=event.id,
                actor_email=event.actor_id,
                actor_type=event.actor_type,
                event_type=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                created_at=event.occurred_at,
                before=event.before,
                after=event.after,
                details=(event.metadata or {}).get("message") or (event.metadata or {}).get("reason"),
            )
            for event in events
        ]

    def record_legacy(
        self,
        event_type: str,
        actor_email: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: str | None = None,
    ) -> None:
        self.record(
            action=event_type,
            actor_email=actor_email,
            entity_type=resource_type,
            entity_id=resource_id,
            details=details,
        )
