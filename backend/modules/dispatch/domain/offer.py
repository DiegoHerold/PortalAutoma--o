from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ExecutionOfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


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
    status: ExecutionOfferStatus
    offered_at: datetime
    expires_at: datetime
    responded_at: datetime | None = None
    rejection_code: RejectionCode | None = None

