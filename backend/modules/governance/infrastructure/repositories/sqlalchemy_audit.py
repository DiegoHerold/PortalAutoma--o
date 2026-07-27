from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.orm.models import AuditEventRecord


class SqlAlchemyAuditEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, event: AuditEvent) -> AuditEvent:
        row = AuditEventRecord(
            id=event.id,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            before=event.before,
            after=event.after,
            metadata_json=event.metadata,
            ip=event.ip,
            user_agent=event.user_agent,
            occurred_at=event.occurred_at or datetime.utcnow(),
        )
        self.db.add(row)
        self.db.flush()
        return event
