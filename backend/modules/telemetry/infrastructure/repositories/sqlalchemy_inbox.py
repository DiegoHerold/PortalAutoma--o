from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.telemetry.infrastructure.orm.models import InboxMessageRecord


class InboxPayloadConflictError(ValueError):
    pass


class SqlAlchemyInboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_once(self, message_id: str, source: str, source_id: str | None, message_type: str, payload: dict[str, Any]) -> bool:
        payload_hash = _payload_hash(payload)
        existing = self.db.get(InboxMessageRecord, message_id)
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise InboxPayloadConflictError("Same message_id was received with a different payload.")
            return False
        row = InboxMessageRecord(
            message_id=message_id,
            source=source,
            source_id=source_id,
            message_type=message_type,
            payload_hash=payload_hash,
            status="received",
            payload=payload,
        )
        self.db.add(row)
        self.db.flush()
        return True

    def mark_processed(self, message_id: str) -> None:
        row = self.db.get(InboxMessageRecord, message_id)
        if row is None:
            return
        row.status = "processed"
        row.processed_at = datetime.now(UTC)
        self.db.add(row)
        self.db.flush()


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
