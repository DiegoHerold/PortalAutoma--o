from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.access.domain.states import UserStatus


@dataclass(frozen=True)
class User:
    id: int | None
    email: str
    name: str
    status: UserStatus
    password_hash: str | None
    organization_id: int | None
    role_id: int | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    disabled_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE


def normalize_email(email: str) -> str:
    return email.strip().lower()

