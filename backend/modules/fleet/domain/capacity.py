from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AgentCapacityRecommendation:
    agent_id: str
    agent_instance_id: str
    observed_at: datetime
    interactive: int = 0
    background: int = 0
    browser: int = 0
    revision: int = 1

    def __post_init__(self) -> None:
        for name in ("interactive", "background", "browser"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} recommendation cannot be negative.")
        if self.revision < 1:
            raise ValueError("Capacity recommendation revision must be positive.")
