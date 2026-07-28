from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.access.domain.states import TeamStatus


@dataclass(frozen=True)
class Team:
    id: int | None
    organization_id: int
    key: str
    name: str
    status: TeamStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None

