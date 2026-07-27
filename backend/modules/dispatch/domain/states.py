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
    RESERVED = "reserved"
    RELEASED = "released"
    CONVERTED = "converted"
    EXPIRED = "expired"


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
