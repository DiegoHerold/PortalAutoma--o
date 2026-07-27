from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class IdempotencyReplayStatus(StrEnum):
    NEW = "new"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    scope: str
    request_hash: str
    response_status: int | None = None
    response_payload: dict[str, Any] | None = None
    resource_id: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None


class IdempotencyStore(Protocol):
    def get(self, scope: str, key: str) -> IdempotencyRecord | None:
        raise NotImplementedError

    def reserve(self, record: IdempotencyRecord) -> IdempotencyReplayStatus:
        raise NotImplementedError

    def save_response(self, scope: str, key: str, status: int, payload: dict[str, Any], resource_id: str | None) -> None:
        raise NotImplementedError
