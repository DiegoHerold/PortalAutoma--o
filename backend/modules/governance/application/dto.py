from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditEventDTO:
    id: str
    organization_id: int | None
    actor_type: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    metadata: dict[str, Any]
    correlation_id: str | None
    ip: str | None
    user_agent: str | None
    occurred_at: datetime | None


@dataclass(frozen=True)
class SecretDTO:
    id: str
    organization_id: int | None
    key: str
    name: str
    description: str | None
    status: str
    current_version_id: str | None
    created_by: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class SecretVersionDTO:
    id: str
    secret_id: str
    version: int
    encryption_key_id: str
    created_by: str | None
    created_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class SecretGrantDTO:
    id: str
    secret_id: str
    grantee_type: str
    grantee_id: str
    permission: str
    created_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class SystemLimitDTO:
    key: str
    value: int
    unit: str
    description: str | None
    organization_id: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RetentionPolicyDTO:
    resource_type: str
    retention_days: int
    archive_after_days: int | None
    delete_after_days: int | None
    legal_hold: bool
    enabled: bool
    organization_id: int | None
    updated_at: datetime | None = None


def to_payload(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
