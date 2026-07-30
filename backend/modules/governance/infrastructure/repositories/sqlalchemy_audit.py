from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.orm.models import AuditEventRecord


class SqlAlchemyAuditEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, event: AuditEvent) -> AuditEvent:
        row = AuditEventRecord(
            id=event.id,
            organization_id=event.organization_id,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            before=event.before,
            after=event.after,
            metadata_json=event.metadata,
            correlation_id=event.correlation_id,
            ip=event.ip,
            user_agent=event.user_agent,
            occurred_at=event.occurred_at or datetime.now(UTC),
        )
        self.db.add(row)
        self.db.flush()
        return event

    def list(
        self,
        *,
        actor: str | None = None,
        query: str | None = None,
        actor_type: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventRecord]:
        stmt = select(AuditEventRecord).order_by(AuditEventRecord.occurred_at.desc())
        if actor:
            stmt = stmt.where(AuditEventRecord.actor_id == actor)
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    AuditEventRecord.actor_id.ilike(pattern),
                    AuditEventRecord.action.ilike(pattern),
                    AuditEventRecord.resource_type.ilike(pattern),
                    AuditEventRecord.resource_id.ilike(pattern),
                    AuditEventRecord.correlation_id.ilike(pattern),
                )
            )
        if actor_type:
            stmt = stmt.where(AuditEventRecord.actor_type == actor_type)
        if resource_type:
            stmt = stmt.where(AuditEventRecord.resource_type == resource_type)
        if action:
            stmt = stmt.where(AuditEventRecord.action == action)
        if occurred_from:
            stmt = stmt.where(AuditEventRecord.occurred_at >= occurred_from)
        if occurred_until:
            stmt = stmt.where(AuditEventRecord.occurred_at < occurred_until)
        return list(self.db.scalars(stmt.limit(limit).offset(offset)).all())

    def facets(self) -> tuple[list[str], list[str], list[str]]:
        return (
            self._distinct_values(AuditEventRecord.action),
            self._distinct_values(AuditEventRecord.resource_type),
            self._distinct_values(AuditEventRecord.actor_type),
        )

    def _distinct_values(self, column) -> list[str]:
        rows = self.db.scalars(select(column).distinct().order_by(column)).all()
        return [value for value in rows if value]
