from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from modules.fleet.domain.value_objects import utcnow


@dataclass(frozen=True)
class FleetEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=utcnow)


def fleet_event(event_type: str, aggregate_id: str, payload: dict[str, Any]) -> FleetEvent:
    return FleetEvent(event_type=event_type, aggregate_type="agent", aggregate_id=aggregate_id, payload=payload)
