from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SystemLimit:
    key: str
    value: int
    unit: str
    description: str | None = None
    organization_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

