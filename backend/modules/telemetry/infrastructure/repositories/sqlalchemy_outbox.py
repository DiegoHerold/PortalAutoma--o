from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.catalog.domain.events import CatalogEvent
from modules.telemetry.infrastructure.orm.models import OutboxMessageRecord


class SqlAlchemyOutboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append_catalog_event(self, event: CatalogEvent) -> None:
        row = OutboxMessageRecord(
            id=str(uuid4()),
            topic="catalog.events",
            message_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            status="pending",
            correlation_id=None,
            causation_id=None,
            available_at=event.occurred_at,
        )
        self.db.add(row)
        self.db.flush()

    def fetch_available_batch(self, limit: int = 100) -> list[OutboxMessageRecord]:
        rows = list(
            self.db.scalars(
                select(OutboxMessageRecord)
                .where(OutboxMessageRecord.status == "pending", OutboxMessageRecord.available_at <= datetime.utcnow())
                .order_by(OutboxMessageRecord.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for row in rows:
            row.status = "processing"
            row.processing_started_at = datetime.utcnow()
            row.attempts += 1
        self.db.flush()
        return rows

    def mark_published(self, message_id: str) -> None:
        row = self.db.get(OutboxMessageRecord, message_id)
        if row is None:
            return
        row.status = "published"
        row.published_at = datetime.utcnow()
        self.db.add(row)
        self.db.flush()

    def mark_failed(self, message_id: str, error: str, max_attempts: int = 5) -> None:
        row = self.db.get(OutboxMessageRecord, message_id)
        if row is None:
            return
        row.last_error = error
        if row.attempts >= max_attempts:
            row.status = "dead_letter"
        else:
            row.status = "failed"
            row.available_at = datetime.utcnow() + timedelta(seconds=min(300, 2 ** row.attempts))
        self.db.add(row)
        self.db.flush()
