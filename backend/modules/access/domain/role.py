from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Role:
    id: int | None
    name: str
    slug: str
    description: str | None = None
    permissions: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

