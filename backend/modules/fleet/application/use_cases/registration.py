from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from modules.fleet.application.dto import ActorDTO, AgentCredentialDTO, AgentDTO, RegistrationResultDTO, RegistrationTokenDTO
from modules.fleet.application.ports import (
    AgentConfigurationRepository,
    AgentCredentialRepository,
    AgentRegistrationTokenRepository,
    AgentRepository,
    FleetOutbox,
    TransactionManager,
)
from modules.fleet.application.use_cases._shared import audit, default_configuration, new_id, outbox, utcnow
from modules.fleet.domain import states
from modules.fleet.domain.errors import AgentCredentialError, AgentDisabledError, AgentRegistrationError, DuplicateAgentRegistrationError
from modules.fleet.domain.value_objects import generate_agent_id, generate_agent_secret, generate_registration_token, hash_secret, secrets_match
from modules.governance.application.ports import AuditEventRepository


class CreateAgentRegistrationToken:
    def __init__(self, tokens: AgentRegistrationTokenRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.tokens = tokens
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, actor: ActorDTO, expires_in_seconds: int = 3600, metadata: dict[str, Any] | None = None) -> RegistrationTokenDTO:
        now = utcnow()
        secret = generate_registration_token()
        token = RegistrationTokenDTO(
            id=new_id("art"),
            token=secret,
            status=states.REGISTRATION_TOKEN_ACTIVE,
            expires_at=now + timedelta(seconds=max(60, expires_in_seconds)),
            created_by=actor.actor_id,
            created_at=now,
            metadata=metadata or {},
        )
        created = self.tokens.add(token, hash_secret(secret))
        audit(self.audit, actor, "agent.registration_token.created", "agent_registration_token", created.id, after={"expires_at": created.expires_at.isoformat()})
        outbox(self.outbox, "agent.registration_token.created", created.id, {"token_id": created.id, "expires_at": created.expires_at.isoformat()})
        self.transaction.commit()
        return replace(created, token=secret)


class RevokeAgentRegistrationToken:
    def __init__(self, tokens: AgentRegistrationTokenRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.tokens = tokens
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, token_id: str, actor: ActorDTO) -> RegistrationTokenDTO:
        token = self.tokens.get(token_id)
        if token is None:
            raise AgentRegistrationError("Registration token not found.")
        if token.status == states.REGISTRATION_TOKEN_USED:
            raise AgentRegistrationError("Used registration tokens cannot be revoked.")
        updated = self.tokens.save(replace(token, status=states.REGISTRATION_TOKEN_REVOKED, revoked_at=utcnow(), token=None))
        audit(self.audit, actor, "agent.registration_token.revoked", "agent_registration_token", token_id)
        outbox(self.outbox, "agent.registration_token.revoked", token_id, {"token_id": token_id})
        self.transaction.commit()
        return updated


class RegisterAgent:
    def __init__(
        self,
        agents: AgentRepository,
        tokens: AgentRegistrationTokenRepository,
        credentials: AgentCredentialRepository,
        configurations: AgentConfigurationRepository,
        audit_repo: AuditEventRepository | None,
        outbox_repo: FleetOutbox | None,
        transaction: TransactionManager,
    ) -> None:
        self.agents = agents
        self.tokens = tokens
        self.credentials = credentials
        self.configurations = configurations
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, registration_token: str, payload: dict[str, Any], actor: ActorDTO | None = None) -> RegistrationResultDTO:
        actor = actor or ActorDTO(actor_type="agent")
        now = utcnow()
        token = self.tokens.get_by_hash(hash_secret(registration_token))
        if token is None:
            raise AgentRegistrationError("Registration token is invalid.")
        if token.status != states.REGISTRATION_TOKEN_ACTIVE or _naive(token.expires_at) <= now:
            raise AgentRegistrationError("Registration token is not usable.")

        local_identity = str(payload.get("local_identity") or payload.get("machine_id") or "").strip()
        hostname = str(payload.get("hostname") or "").strip()
        requested_name = str(payload.get("name") or "").strip()
        if not local_identity or not hostname:
            raise AgentRegistrationError("local_identity and hostname are required.")

        machine_fingerprint = payload.get("machine_fingerprint")
        existing = self.agents.get_by_local_identity(local_identity)
        if existing is None and machine_fingerprint:
            by_fingerprint = self.agents.get_by_machine_fingerprint(str(machine_fingerprint))
            if by_fingerprint is not None:
                raise DuplicateAgentRegistrationError("Machine fingerprint is already registered to another Agent.")

        if existing is None:
            agent = AgentDTO(
                id=generate_agent_id(),
                name=requested_name or hostname,
                hostname=hostname,
                enabled=True,
                connectivity_status="offline",
                administrative_status="enabled",
                health_status="healthy",
                occupancy_status="idle",
                current_version=payload.get("agent_version"),
                desired_version=None,
                protocol_version=None,
                created_at=now,
                updated_at=now,
                last_seen_at=None,
                disabled_at=None,
                local_identity=local_identity,
                machine_fingerprint=str(machine_fingerprint) if machine_fingerprint else None,
            )
            agent = self.agents.add(agent)
            self.configurations.save(default_configuration(agent.id))
        else:
            agent = self.agents.save(
                replace(
                    existing,
                    hostname=hostname,
                    name=requested_name or existing.name or hostname,
                    current_version=payload.get("agent_version") or existing.current_version,
                    machine_fingerprint=str(machine_fingerprint) if machine_fingerprint else existing.machine_fingerprint,
                    updated_at=now,
                )
            )

        token = self.tokens.save(replace(token, status=states.REGISTRATION_TOKEN_USED, used_at=now, used_by_agent_id=agent.id, token=None))
        credential = _issue_credential(self.credentials, agent.id, now)
        configuration = self.configurations.get(agent.id) or default_configuration(agent.id)
        audit(self.audit, actor, "agent.registered", "agent", agent.id, after={"hostname": agent.hostname})
        audit(self.audit, actor, "agent.credential.issued", "agent_credential", credential.id, after={"agent_id": agent.id})
        outbox(self.outbox, "agent.registered", agent.id, {"agent_id": agent.id})
        self.transaction.commit()
        return RegistrationResultDTO(
            agent=agent,
            credential=credential,
            heartbeat_interval_seconds=configuration.heartbeat_interval_seconds,
            stale_after_seconds=configuration.stale_after_seconds,
            offline_after_seconds=configuration.offline_after_seconds,
        )


class ValidateAgentCredential:
    def __init__(self, agents: AgentRepository, credentials: AgentCredentialRepository, transaction: TransactionManager) -> None:
        self.agents = agents
        self.credentials = credentials
        self.transaction = transaction

    def execute(self, public_identifier: str, secret: str) -> AgentDTO:
        found = self.credentials.get_by_public_identifier(public_identifier)
        if found is None:
            raise AgentCredentialError("Agent credential is invalid.")
        credential, secret_hash = found
        now = utcnow()
        if not secrets_match(secret, secret_hash):
            raise AgentCredentialError("Agent credential is invalid.")
        if credential.status != states.CREDENTIAL_ACTIVE or (credential.expires_at is not None and _naive(credential.expires_at) <= now):
            raise AgentCredentialError("Agent credential is not active.")
        agent = self.agents.get(credential.agent_id)
        if agent is None:
            raise AgentCredentialError("Agent credential is orphaned.")
        if not agent.enabled or agent.administrative_status == "disabled":
            raise AgentDisabledError("Agent is disabled.")
        self.credentials.save(replace(credential, last_used_at=now))
        self.transaction.commit()
        return agent


class RotateAgentCredential:
    def __init__(self, credentials: AgentCredentialRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.credentials = credentials
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO) -> AgentCredentialDTO:
        now = utcnow()
        for credential in self.credentials.active_for_agent(agent_id):
            self.credentials.save(replace(credential, status=states.CREDENTIAL_ROTATED, rotated_at=now))
        issued = _issue_credential(self.credentials, agent_id, now)
        audit(self.audit, actor, "agent.credential.rotated", "agent", agent_id, after={"credential_id": issued.id})
        outbox(self.outbox, "agent.credential.rotated", agent_id, {"agent_id": agent_id, "credential_id": issued.id})
        self.transaction.commit()
        return issued


class RevokeAgentCredential:
    def __init__(self, credentials: AgentCredentialRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.credentials = credentials
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, credential_id: str, actor: ActorDTO) -> AgentCredentialDTO:
        credential = self.credentials.get(credential_id)
        if credential is None or credential.agent_id != agent_id:
            raise AgentCredentialError("Agent credential not found.")
        updated = self.credentials.save(replace(credential, status=states.CREDENTIAL_REVOKED, revoked_at=utcnow()))
        audit(self.audit, actor, "agent.credential.revoked", "agent_credential", credential_id)
        outbox(self.outbox, "agent.credential.revoked", agent_id, {"agent_id": agent_id, "credential_id": credential_id})
        self.transaction.commit()
        return updated


def _issue_credential(credentials: AgentCredentialRepository, agent_id: str, now: datetime) -> AgentCredentialDTO:
    secret = generate_agent_secret()
    credential = AgentCredentialDTO(
        id=new_id("acr"),
        agent_id=agent_id,
        credential_type="bearer_token",
        public_identifier=new_id("acp"),
        status=states.CREDENTIAL_ACTIVE,
        issued_at=now,
        expires_at=None,
        last_used_at=None,
        rotated_at=None,
        revoked_at=None,
        secret=secret,
    )
    return credentials.add(credential, hash_secret(secret))


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
