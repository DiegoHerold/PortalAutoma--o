from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AgentResourceSnapshot:
    id: str
    agent_id: str
    agent_instance_id: str
    observed_at: datetime
    cpu_usage_percentage: float | None = None
    memory_total_mb: int | None = None
    memory_available_mb: int | None = None
    memory_usage_percentage: float | None = None
    disk_free_mb: int | None = None
    disk_usage_percentage: float | None = None
    process_count: int | None = None
    uptime_seconds: int | None = None
    revision: int = 1
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("cpu_usage_percentage", "memory_usage_percentage", "disk_usage_percentage"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")
        if self.revision < 1:
            raise ValueError("Resource snapshot revision must be positive.")

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now
