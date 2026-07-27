from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from modules.dispatch.domain.states import ResourceReservationStatus


@dataclass(frozen=True)
class ResourceReservation:
    id: str
    execution_offer_id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    pool_type: str
    quantity: int
    status: ResourceReservationStatus
    expires_at: datetime
    created_at: datetime
    released_at: datetime | None = None
    converted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        execution_offer_id: str,
        execution_attempt_id: str,
        agent_id: str,
        agent_instance_id: str,
        pool_type: str,
        quantity: int,
        expires_at: datetime,
        now: datetime,
    ) -> "ResourceReservation":
        if pool_type not in {"interactive", "background", "browser"}:
            raise ValueError("Unsupported reservation pool.")
        if quantity <= 0:
            raise ValueError("Reservation quantity must be positive.")
        return cls(
            id=id,
            execution_offer_id=execution_offer_id,
            execution_attempt_id=execution_attempt_id,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            pool_type=pool_type,
            quantity=quantity,
            status=ResourceReservationStatus.RESERVED,
            expires_at=expires_at,
            created_at=now,
        )

    def release(self, now: datetime) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.RELEASED:
            return self
        return replace(self, status=ResourceReservationStatus.RELEASED, released_at=now)

    def convert_to_usage(self, now: datetime) -> "ResourceReservation":
        if self.status == ResourceReservationStatus.CONVERTED:
            return self
        return replace(self, status=ResourceReservationStatus.CONVERTED, converted_at=now)
