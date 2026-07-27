from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from modules.orchestration.application.dto import AgentSelectionDTO, AgentSelectionRequestDTO, ExecutionOfferDTO, ResourceReservationDTO


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


class AgentSelectionPort(Protocol):
    def select(self, request: AgentSelectionRequestDTO) -> AgentSelectionDTO:
        raise NotImplementedError


class ExecutionOfferRepository(Protocol):
    def add(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        raise NotImplementedError

    def save(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        raise NotImplementedError

    def get(self, offer_id: str) -> ExecutionOfferDTO | None:
        raise NotImplementedError


class OfferReservationPort(Protocol):
    def reserve(self, reservation: ResourceReservationDTO) -> ResourceReservationDTO:
        raise NotImplementedError

    def release_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError

    def convert_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError


class DispatchOutbox(Protocol):
    def append_event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any], correlation_id: str | None = None, causation_id: str | None = None) -> None:
        raise NotImplementedError
