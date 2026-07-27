from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CatalogEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    occurred_at: datetime = field(default_factory=datetime.utcnow)


def automation_event(event_type: str, automation_id: str, payload: dict[str, Any]) -> CatalogEvent:
    return CatalogEvent(
        event_type=event_type,
        aggregate_type="Automation",
        aggregate_id=automation_id,
        payload=payload,
    )


def automation_version_event(event_type: str, version_id: str, payload: dict[str, Any]) -> CatalogEvent:
    return CatalogEvent(
        event_type=event_type,
        aggregate_type="AutomationVersion",
        aggregate_id=version_id,
        payload=payload,
    )
