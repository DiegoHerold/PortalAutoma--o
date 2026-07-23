from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.audit import AuditLog
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_logs = AuditRepository(db)

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
        """
        Record an audit event.
        
        Args:
            action: The action performed (event_type)
            actor_email: Email of the user who performed the action
            actor_type: Type of actor (user, system, trigger, worker)
            entity_type: Type of entity being acted upon (resource_type)
            entity_id: ID of the entity (resource_id)
            resource_type: Backwards-compatible alias for entity_type
            resource_id: Backwards-compatible alias for entity_id
            details: Additional details about the action
            before: State before the change (for updates)
            after: State after the change (for updates)
        """
        audit_log = AuditLog(
            event_type=action,
            actor_email=actor_email,
            actor_type=actor_type,
            resource_type=entity_type or resource_type,
            resource_id=entity_id or resource_id,
            details=details,
            before=before,
            after=after,
        )
        self.audit_logs.create(audit_log)

    def get_audit_logs(
        self,
        actor: str | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Get audit logs with optional filtering."""
        query = self.db.query(AuditLog)
        
        if actor:
            query = query.filter(AuditLog.actor_email.ilike(f"%{actor}%"))
        if entity_type:
            query = query.filter(AuditLog.resource_type == entity_type)
        if action:
            query = query.filter(AuditLog.event_type == action)
        
        return query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()

    # Legacy method for compatibility
    def record_legacy(
        self,
        event_type: str,
        actor_email: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: str | None = None,
    ) -> None:
        """Legacy method for backward compatibility."""
        self.record(
            action=event_type,
            actor_email=actor_email,
            entity_type=resource_type,
            entity_id=resource_id,
            details=details,
        )
