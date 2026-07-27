from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from modules.fleet.domain import states
from modules.fleet.domain.errors import AgentCredentialError, AgentRegistrationError


@dataclass
class AgentRegistrationToken:
    id: str
    token_hash: str
    status: str
    expires_at: datetime
    created_by: str | None
    created_at: datetime
    used_at: datetime | None = None
    used_by_agent_id: str | None = None
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def ensure_usable(self, now: datetime) -> None:
        if self.status == states.REGISTRATION_TOKEN_REVOKED:
            raise AgentRegistrationError("Registration token was revoked.")
        if self.status == states.REGISTRATION_TOKEN_USED:
            raise AgentRegistrationError("Registration token was already used.")
        if self.status == states.REGISTRATION_TOKEN_EXPIRED or self.expires_at <= now:
            raise AgentRegistrationError("Registration token is expired.")
        if self.status != states.REGISTRATION_TOKEN_ACTIVE:
            raise AgentRegistrationError("Registration token is not active.")

    def mark_used(self, agent_id: str, now: datetime) -> None:
        self.used_by_agent_id = agent_id
        self.used_at = now
        self.status = states.REGISTRATION_TOKEN_USED

    def revoke(self, now: datetime) -> None:
        if self.status == states.REGISTRATION_TOKEN_USED:
            raise AgentRegistrationError("Used registration tokens cannot be revoked.")
        self.status = states.REGISTRATION_TOKEN_REVOKED
        self.revoked_at = now


@dataclass
class AgentCredential:
    id: str
    agent_id: str
    credential_type: str
    public_identifier: str
    secret_hash: str
    status: str
    issued_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None

    def ensure_usable(self, now: datetime) -> None:
        if self.status == states.CREDENTIAL_REVOKED:
            raise AgentCredentialError("Agent credential was revoked.")
        if self.status == states.CREDENTIAL_ROTATED:
            raise AgentCredentialError("Agent credential was rotated.")
        if self.status == states.CREDENTIAL_EXPIRED or (self.expires_at is not None and self.expires_at <= now):
            raise AgentCredentialError("Agent credential is expired.")
        if self.status != states.CREDENTIAL_ACTIVE:
            raise AgentCredentialError("Agent credential is not active.")

    def mark_used(self, now: datetime) -> None:
        self.last_used_at = now

    def rotate(self, now: datetime) -> None:
        self.status = states.CREDENTIAL_ROTATED
        self.rotated_at = now

    def revoke(self, now: datetime) -> None:
        self.status = states.CREDENTIAL_REVOKED
        self.revoked_at = now
