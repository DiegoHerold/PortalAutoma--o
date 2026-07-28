from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import select

from infrastructure.database import SessionLocal
from modules.telemetry.infrastructure.orm.models import OutboxMessageRecord
from modules.telemetry.infrastructure.repositories.sqlalchemy_outbox import SqlAlchemyOutboxRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboxWorkerConfig:
    batch_size: int = 50
    poll_interval_seconds: float = 1.0
    stuck_processing_seconds: int = 300
    max_attempts: int = 5


class InternalEventDispatcher:
    def publish(self, message: OutboxMessageRecord) -> None:
        logger.info(
            "outbox.message.published",
            extra={
                "message_id": message.id,
                "topic": message.topic,
                "message_type": message.message_type,
                "aggregate_type": message.aggregate_type,
                "aggregate_id": message.aggregate_id,
            },
        )


class OutboxWorker:
    def __init__(self, dispatcher: InternalEventDispatcher | None = None, config: OutboxWorkerConfig | None = None) -> None:
        self.dispatcher = dispatcher or InternalEventDispatcher()
        self.config = config or OutboxWorkerConfig()
        self._stopping = False

    def stop(self) -> None:
        self._stopping = True

    def run_forever(self) -> None:
        while not self._stopping:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_interval_seconds)

    def run_once(self) -> int:
        with SessionLocal() as db:
            self._recover_stuck_messages(db)
            repository = SqlAlchemyOutboxRepository(db)
            messages = repository.fetch_available_batch(self.config.batch_size)
            db.commit()

        processed = 0
        for message in messages:
            with SessionLocal() as db:
                repository = SqlAlchemyOutboxRepository(db)
                current = db.get(OutboxMessageRecord, message.id)
                if current is None:
                    continue
                try:
                    self.dispatcher.publish(current)
                except Exception as exc:  # noqa: BLE001
                    repository.mark_failed(current.id, str(exc), self.config.max_attempts)
                else:
                    repository.mark_published(current.id)
                    processed += 1
                db.commit()
        return processed

    def _recover_stuck_messages(self, db) -> None:
        from datetime import datetime, timedelta

        threshold = datetime.utcnow() - timedelta(seconds=self.config.stuck_processing_seconds)
        rows = db.scalars(
            select(OutboxMessageRecord).where(
                OutboxMessageRecord.status == "processing",
                OutboxMessageRecord.processing_started_at <= threshold,
            )
        ).all()
        for row in rows:
            row.status = "pending"
            row.processing_started_at = None
            db.add(row)
        if rows:
            db.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    OutboxWorker().run_forever()
