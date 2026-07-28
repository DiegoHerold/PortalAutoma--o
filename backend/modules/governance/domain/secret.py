from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Secret:
    id: str
    organization_id: int | None
    key: str
    name: str
    description: str | None
    status: str
    current_version_id: str | None
    created_by: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SecretVersion:
    id: str
    secret_id: str
    version: int
    encrypted_value: str
    encryption_key_id: str
    created_by: str | None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class SecretGrant:
    id: str
    secret_id: str
    grantee_type: str
    grantee_id: str
    permission: str
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


SECRET_STATUSES = ("active", "disabled", "revoked", "archived")
SECRET_GRANT_PERMISSIONS = ("read_metadata", "use", "manage")

