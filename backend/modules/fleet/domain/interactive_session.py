from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InteractiveSessionSnapshot:
    agent_id: str
    agent_instance_id: str
    available: bool | None
    locked: bool | None
    observed_at: datetime
    user: str | None = None
    session_id: str | None = None
    session_type: str | None = None
    expires_at: datetime | None = None

    @property
    def state(self) -> str:
        if self.available is None:
            return "unknown"
        if not self.available:
            return "unavailable"
        return "available_locked" if self.locked else "available_unlocked"
