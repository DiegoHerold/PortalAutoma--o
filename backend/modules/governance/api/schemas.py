from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: str
    organization_id: int | None = None
    actor_type: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    occurred_at: datetime | None = None


class AuditEntryResponse(BaseModel):
    id: str
    actor: str | None = None
    actor_type: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    created_at: datetime | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    message: str | None = None


class SecretCreateRequest(BaseModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    description: str | None = None
    organization_id: int | None = None
    expires_at: datetime | None = None


class SecretRotateRequest(BaseModel):
    value: str = Field(min_length=1)
    expires_at: datetime | None = None


class SecretResponse(BaseModel):
    id: str
    organization_id: int | None = None
    key: str
    name: str
    description: str | None = None
    status: str
    current_version_id: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SecretVersionResponse(BaseModel):
    id: str
    secret_id: str
    version: int
    encryption_key_id: str
    created_by: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class SecretWithVersionResponse(BaseModel):
    secret: SecretResponse
    version: SecretVersionResponse


class SecretGrantCreateRequest(BaseModel):
    grantee_type: str = Field(min_length=1)
    grantee_id: str = Field(min_length=1)
    permission: str = Field(min_length=1)
    expires_at: datetime | None = None


class SecretGrantResponse(BaseModel):
    id: str
    secret_id: str
    grantee_type: str
    grantee_id: str
    permission: str
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class SystemLimitUpsertRequest(BaseModel):
    key: str = Field(min_length=1)
    value: int = Field(ge=0)
    unit: str = Field(min_length=1)
    description: str | None = None
    organization_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemLimitResponse(BaseModel):
    key: str
    value: int
    unit: str
    description: str | None = None
    organization_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


class RetentionPolicyUpsertRequest(BaseModel):
    resource_type: str = Field(min_length=1)
    retention_days: int = Field(ge=0)
    archive_after_days: int | None = Field(default=None, ge=0)
    delete_after_days: int | None = Field(default=None, ge=0)
    legal_hold: bool = False
    enabled: bool = True
    organization_id: int | None = None


class RetentionPolicyResponse(BaseModel):
    resource_type: str
    retention_days: int
    archive_after_days: int | None = None
    delete_after_days: int | None = None
    legal_hold: bool
    enabled: bool
    organization_id: int | None = None
    updated_at: datetime | None = None
