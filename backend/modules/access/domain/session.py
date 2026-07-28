from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserSession:
    id: str
    user_id: int
    token_hash: str
    status: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None

