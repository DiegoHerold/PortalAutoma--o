from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CapabilityRequirement:
    key: str
    version: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentCapability:
    key: str
    status: CapabilityStatus
    observed_at: datetime
    id: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None
    version: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    source: str | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.key or "." not in self.key:
            raise ValueError("Capability key must be a dotted identifier.")
        if self.revision < 1:
            raise ValueError("Capability revision must be positive.")

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now
