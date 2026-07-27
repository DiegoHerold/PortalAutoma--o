from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from modules.dispatch.domain.errors import InvalidOfferTransition, OfferExpired, OfferSecurityError
from modules.dispatch.domain.states import OFFER_TRANSITIONS, ExecutionOfferStatus


class RejectionCode(StrEnum):
    INSUFFICIENT_MEMORY = "INSUFFICIENT_MEMORY"
    INSUFFICIENT_DISK = "INSUFFICIENT_DISK"
    INSUFFICIENT_CPU_CAPACITY = "INSUFFICIENT_CPU_CAPACITY"
    INTERACTIVE_SESSION_UNAVAILABLE = "INTERACTIVE_SESSION_UNAVAILABLE"
    INTERACTIVE_SESSION_LOCKED = "INTERACTIVE_SESSION_LOCKED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"
    AGENT_DRAINING = "AGENT_DRAINING"
    AGENT_DISABLED = "AGENT_DISABLED"
    AGENT_OVERLOADED = "AGENT_OVERLOADED"
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    PACKAGE_UNAVAILABLE = "PACKAGE_UNAVAILABLE"
    RUNTIME_PREPARATION_FAILED = "RUNTIME_PREPARATION_FAILED"
    PACKAGE_PREPARATION_FAILED = "PACKAGE_PREPARATION_FAILED"
    PROTOCOL_INCOMPATIBLE = "PROTOCOL_INCOMPATIBLE"


@dataclass(frozen=True)
class ExecutionOffer:
    id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    status: ExecutionOfferStatus
    requirements_snapshot: dict[str, Any]
    offered_at: datetime
    expires_at: datetime
    responded_at: datetime | None = None
    accepted_at: datetime | None = None
    committed_at: datetime | None = None
    rejection_code: RejectionCode | None = None
    rejection_details: dict[str, Any] | None = None
    correlation_id: str | None = None
    commit_token_hash: str | None = None
    commit_token_expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        execution_attempt_id: str,
        agent_id: str,
        agent_instance_id: str,
        requirements_snapshot: dict[str, Any],
        offered_at: datetime,
        expires_at: datetime,
        correlation_id: str | None = None,
    ) -> "ExecutionOffer":
        if expires_at <= offered_at:
            raise ValueError("Offer expiration must be after offered_at.")
        return cls(
            id=id,
            execution_attempt_id=execution_attempt_id,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            status=ExecutionOfferStatus.PENDING,
            requirements_snapshot=requirements_snapshot,
            offered_at=offered_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )

    def accept(self, *, agent_id: str, agent_instance_id: str, now: datetime) -> "ExecutionOffer":
        self._ensure_recipient(agent_id, agent_instance_id)
        self._ensure_not_expired(now)
        if self.status == ExecutionOfferStatus.ACCEPTED:
            return self
        return self._transition(ExecutionOfferStatus.ACCEPTED, responded_at=now, accepted_at=now)

    def reject(
        self,
        *,
        agent_id: str,
        agent_instance_id: str,
        code: RejectionCode,
        details: dict[str, Any] | None,
        now: datetime,
    ) -> "ExecutionOffer":
        self._ensure_recipient(agent_id, agent_instance_id)
        if self.status == ExecutionOfferStatus.REJECTED:
            return self
        return self._transition(
            ExecutionOfferStatus.REJECTED,
            responded_at=now,
            rejection_code=code,
            rejection_details=details or {},
        )

    def expire(self, now: datetime) -> "ExecutionOffer":
        if self.status == ExecutionOfferStatus.EXPIRED:
            return self
        return self._transition(ExecutionOfferStatus.EXPIRED, responded_at=self.responded_at or now)

    def commit(self, *, token_hash: str, token_expires_at: datetime, now: datetime) -> "ExecutionOffer":
        self._ensure_not_expired(now)
        if self.status == ExecutionOfferStatus.COMMITTED:
            return self
        return self._transition(
            ExecutionOfferStatus.COMMITTED,
            committed_at=now,
            commit_token_hash=self.commit_token_hash or token_hash,
            commit_token_expires_at=self.commit_token_expires_at or token_expires_at,
        )

    def _ensure_recipient(self, agent_id: str, agent_instance_id: str) -> None:
        if self.agent_id != agent_id or self.agent_instance_id != agent_instance_id:
            raise OfferSecurityError("Offer belongs to another Agent or AgentInstance.")

    def _ensure_not_expired(self, now: datetime) -> None:
        if _naive(self.expires_at) <= _naive(now):
            raise OfferExpired("ExecutionOffer has expired.")

    def _transition(self, status: ExecutionOfferStatus, **changes: Any) -> "ExecutionOffer":
        if status not in OFFER_TRANSITIONS.get(self.status, set()):
            raise InvalidOfferTransition(f"ExecutionOffer cannot transition from {self.status} to {status}.")
        return replace(self, status=status, **changes)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value
