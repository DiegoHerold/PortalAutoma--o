from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.shared.application.idempotency import IdempotencyRecord, IdempotencyReplayStatus
from modules.shared.infrastructure.orm.models import IdempotencyRecordModel


class SqlAlchemyIdempotencyStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, scope: str, key: str) -> IdempotencyRecord | None:
        row = self.db.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.scope == scope,
                IdempotencyRecordModel.key == key,
            )
        )
        return _to_domain(row) if row else None

    def reserve(self, record: IdempotencyRecord) -> IdempotencyReplayStatus:
        existing = self.get(record.scope, record.key)
        if existing is not None:
            return (
                IdempotencyReplayStatus.REPLAY
                if existing.request_hash == record.request_hash
                else IdempotencyReplayStatus.CONFLICT
            )
        row = IdempotencyRecordModel(
            key=record.key,
            scope=record.scope,
            request_hash=record.request_hash,
            response_status=record.response_status,
            response_payload=record.response_payload,
            resource_id=record.resource_id,
            expires_at=record.expires_at,
        )
        self.db.add(row)
        self.db.flush()
        return IdempotencyReplayStatus.NEW

    def save_response(self, scope: str, key: str, status: int, payload: dict, resource_id: str | None) -> None:
        row = self.db.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.scope == scope,
                IdempotencyRecordModel.key == key,
            )
        )
        if row is None:
            return
        row.response_status = status
        row.response_payload = payload
        row.resource_id = resource_id
        self.db.add(row)
        self.db.flush()


def _to_domain(row: IdempotencyRecordModel) -> IdempotencyRecord:
    return IdempotencyRecord(
        key=row.key,
        scope=row.scope,
        request_hash=row.request_hash,
        response_status=row.response_status,
        response_payload=row.response_payload,
        resource_id=row.resource_id,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )
