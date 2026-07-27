from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class InboxMessageStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    message_type: str
    received_at: datetime
    status: InboxMessageStatus
    payload: dict


class InboxStore(Protocol):
    def record_once(self, message: InboxMessage) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    message_type: str
    payload: dict
    created_at: datetime


class TransactionalOutbox(Protocol):
    def append(self, message: OutboxMessage) -> None:
        raise NotImplementedError

