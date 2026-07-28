from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RetentionPolicy:
    resource_type: str
    retention_days: int
    archive_after_days: int | None
    delete_after_days: int | None
    legal_hold: bool
    enabled: bool
    organization_id: int | None = None
    updated_at: datetime | None = None

