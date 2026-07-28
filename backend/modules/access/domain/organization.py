from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.access.domain.states import OrganizationStatus


@dataclass(frozen=True)
class Organization:
    id: int | None
    key: str
    name: str
    status: OrganizationStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None

