from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentConfiguration:
    agent_id: str
    heartbeat_interval_seconds: int = 30
    stale_after_seconds: int = 90
    offline_after_seconds: int = 180
    administrator_pool_limits: dict[str, int | None] = field(default_factory=dict)
    enabled_pools: list[str] = field(default_factory=lambda: ["interactive", "background", "browser"])
    allowlist_capabilities: list[str] = field(default_factory=list)
    maintenance: bool = False
    desired_version: str | None = None
    restrictions: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.heartbeat_interval_seconds < 5:
            raise ValueError("Heartbeat interval must be at least 5 seconds.")
        if self.stale_after_seconds <= self.heartbeat_interval_seconds:
            raise ValueError("stale_after_seconds must be greater than heartbeat interval.")
        if self.offline_after_seconds <= self.stale_after_seconds:
            raise ValueError("offline_after_seconds must be greater than stale_after_seconds.")
