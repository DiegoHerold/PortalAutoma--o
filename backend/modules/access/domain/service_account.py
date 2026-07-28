from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from modules.access.domain.states import ServiceAccountStatus


@dataclass(frozen=True)
class ServiceAccount:
    id: str
    organization_id: int | None
    name: str
    status: ServiceAccountStatus
    credential_hash: str
    permissions: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

