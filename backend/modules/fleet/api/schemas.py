from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateRegistrationTokenRequest(BaseModel):
    expires_in_seconds: int = Field(default=3600, ge=60, le=60 * 60 * 24 * 30)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegisterAgentRequest(BaseModel):
    registration_token: str
    local_identity: str
    hostname: str
    name: str | None = None
    machine_fingerprint: str | None = None
    agent_version: str | None = None
    operating_system: str | None = None
    architecture: str | None = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list)


class RotateCredentialResponse(BaseModel):
    id: str
    agent_id: str
    public_identifier: str
    secret: str
    bearer_token: str


class RevokeCredentialRequest(BaseModel):
    credential_id: str


class StartAgentInstanceRequest(BaseModel):
    agent_version: str | None = None
    process_started_at: str | None = None


class MaintenanceRequest(BaseModel):
    enabled: bool = True


class DisableAgentRequest(BaseModel):
    reason: str | None = None


class AgentConfigurationPatchRequest(BaseModel):
    heartbeat_interval_seconds: int | None = None
    stale_after_seconds: int | None = None
    offline_after_seconds: int | None = None
    administrator_pool_limits: dict[str, int | None] | None = None
    enabled_pools: list[str] | None = None
    allowlist_capabilities: list[str] | None = None
    maintenance: bool | None = None
    desired_version: str | None = None
    restrictions: dict[str, Any] | None = None


class AgentPatchRequest(BaseModel):
    name: str | None = None
    desired_version: str | None = None
    configuration: AgentConfigurationPatchRequest | None = None


class AgentUpdateRequest(BaseModel):
    desired_version: str


class AgentCommandRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
