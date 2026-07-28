from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from modules.dispatch.domain.states import ResourceReservationStatus


@dataclass(frozen=True)
class ResourceReservation:
    id: str
    task_execution_id: str
    execution_offer_id: str | None
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    pool_type: str
    units: int
    status: ResourceReservationStatus
    expires_at: datetime
    reserved_at: datetime
    activated_at: datetime | None = None
    released_at: datetime | None = None
    release_reason: str | None = None

    @property
    def quantity(self) -> int:
        return self.units

    @property
    def created_at(self) -> datetime:
        return self.reserved_at

    @property
    def converted_at(self) -> datetime | None:
        return self.activated_at

    @classmethod
    def create(
        cls,
        *,
        id: str,
        task_execution_id: str,
        execution_offer_id: str | None,
        execution_attempt_id: str,
        agent_id: str,
        agent_instance_id: str,
        pool_type: str,
        units: int | None = None,
        quantity: int | None = None,
        expires_at: datetime,
        now: datetime,
    ) -> "ResourceReservation":
        if pool_type not in {"interactive", "background", "browser"}:
            raise ValueError("Unsupported reservation pool.")
        requested_units = units if units is not None else quantity if quantity is not None else 1
        if requested_units <= 0:
            raise ValueError("Reservation quantity must be positive.")
        return cls(
            id=id,
            task_execution_id=task_execution_id,
            execution_offer_id=execution_offer_id,
            execution_attempt_id=execution_attempt_id,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            pool_type=pool_type,
            units=requested_units,
            status=ResourceReservationStatus.PENDING,
            expires_at=expires_at,
            reserved_at=now,
        )

    def release(self, now: datetime, reason: str | None = None) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.RELEASED:
            return self
        return replace(self, status=ResourceReservationStatus.RELEASED, released_at=now, release_reason=reason)

    def cancel(self, now: datetime, reason: str | None = None) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.CANCELLED:
            return self
        return replace(self, status=ResourceReservationStatus.CANCELLED, released_at=now, release_reason=reason)

    def expire(self, now: datetime) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.EXPIRED:
            return self
        return replace(self, status=ResourceReservationStatus.EXPIRED, released_at=now, release_reason="expired")

    def activate(self, now: datetime) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.ACTIVE:
            return self
        return replace(self, status=ResourceReservationStatus.ACTIVE, activated_at=self.activated_at or now)

    def convert_to_usage(self, now: datetime) -> "ResourceReservation":
        return self.activate(now)
