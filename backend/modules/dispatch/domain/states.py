from __future__ import annotations

from enum import StrEnum


class ExecutionOfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class ResourceReservationStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ResourceLockStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ExecutionLeaseStatus(StrEnum):
    ACTIVE = "active"
    SUSPECT = "suspect"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPLETED = "completed"


class DispatchDecisionStatus(StrEnum):
    SELECTED = "selected"
    NO_CANDIDATE = "no_candidate"
    SKIPPED = "skipped"
    ERROR = "error"


class RetryScheduleStatus(StrEnum):
    SCHEDULED = "scheduled"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CancellationRequestStatus(StrEnum):
    REQUESTED = "requested"
    COMMAND_SENT = "command_sent"
    CONFIRMED = "confirmed"
    FORCE_REQUIRED = "force_required"
    FORCED = "forced"
    FAILED = "failed"


class ReconciliationStatus(StrEnum):
    RECORDED = "recorded"
    APPLIED = "applied"
    NEEDS_ATTENTION = "needs_attention"


OFFER_TRANSITIONS: dict[ExecutionOfferStatus, set[ExecutionOfferStatus]] = {
    ExecutionOfferStatus.PENDING: {
        ExecutionOfferStatus.ACCEPTED,
        ExecutionOfferStatus.REJECTED,
        ExecutionOfferStatus.EXPIRED,
        ExecutionOfferStatus.CANCELLED,
    },
    ExecutionOfferStatus.ACCEPTED: {
        ExecutionOfferStatus.COMMITTED,
        ExecutionOfferStatus.EXPIRED,
        ExecutionOfferStatus.CANCELLED,
    },
    ExecutionOfferStatus.COMMITTED: set(),
    ExecutionOfferStatus.REJECTED: set(),
    ExecutionOfferStatus.EXPIRED: set(),
    ExecutionOfferStatus.CANCELLED: set(),
}
