from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class AgentCommandStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AgentCommand:
    id: str
    agent_id: str
    agent_instance_id: str | None
    command_sequence: int
    message_type: str
    payload: dict
    status: AgentCommandStatus
    created_at: datetime
    available_at: datetime | None = None
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    expires_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None


class AgentCommandStore(Protocol):
    def append(self, command: AgentCommand) -> None:
        raise NotImplementedError

    def next_pending_for_agent(self, agent_id: str) -> AgentCommand | None:
        raise NotImplementedError
