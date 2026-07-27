from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AgentPool:
    agent_id: str
    pool_type: str
    observed_at: datetime
    recommended_total: int | None = None
    administrator_total: int | None = None
    effective_total: int = 0
    used: int = 0
    reserved: int = 0
    revision: int = 1

    @property
    def available(self) -> int:
        return max(0, self.effective_total - self.used - self.reserved)

    def __post_init__(self) -> None:
        for name in ("effective_total", "used", "reserved"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative.")
        if self.revision < 1:
            raise ValueError("Pool revision must be positive.")
