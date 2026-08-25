from __future__ import annotations

from datetime import timedelta

from modules.fleet.application.dto import AgentCredentialDTO, AgentDTO, RegistrationTokenDTO
from modules.fleet.application.use_cases._shared import default_configuration, utcnow
from modules.fleet.application.use_cases.registration import RegisterAgent
from modules.fleet.domain import states
from modules.fleet.domain.value_objects import hash_secret


class AgentRepo:
    def __init__(self, agent: AgentDTO) -> None:
        self.agent = agent

    def add(self, agent: AgentDTO) -> AgentDTO:
        self.agent = agent
        return agent

    def save(self, agent: AgentDTO) -> AgentDTO:
        self.agent = agent
        return agent

    def get(self, agent_id: str) -> AgentDTO | None:
        return self.agent if self.agent.id == agent_id else None

    def get_by_local_identity(self, local_identity: str) -> AgentDTO | None:
        return self.agent if self.agent.local_identity == local_identity else None

    def get_by_machine_fingerprint(self, machine_fingerprint: str) -> AgentDTO | None:
        return self.agent if self.agent.machine_fingerprint == machine_fingerprint else None


class TokenRepo:
    def __init__(self, secret: str) -> None:
        now = utcnow()
        self.secret_hash = hash_secret(secret)
        self.token = RegistrationTokenDTO(
            id="art_1",
            status=states.REGISTRATION_TOKEN_ACTIVE,
            expires_at=now + timedelta(minutes=5),
            created_by="test",
            created_at=now,
            token=secret,
        )

    def get_by_hash(self, token_hash: str) -> RegistrationTokenDTO | None:
        return self.token if token_hash == self.secret_hash else None

    def save(self, token: RegistrationTokenDTO) -> RegistrationTokenDTO:
        self.token = token
        return token


class CredentialRepo:
    def add(self, credential: AgentCredentialDTO, secret_hash: str) -> AgentCredentialDTO:
        return credential


class ConfigurationRepo:
    def __init__(self, agent_id: str) -> None:
        self.config = default_configuration(agent_id)

    def get(self, agent_id: str):
        return self.config if self.config.agent_id == agent_id else None

    def save(self, configuration):
        self.config = configuration
        return configuration


class Transaction:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def test_existing_agent_registration_updates_explicit_name() -> None:
    now = utcnow()
    existing = AgentDTO(
        id="agt_existing",
        name="MAQ65",
        hostname="MAQ65",
        enabled=True,
        connectivity_status="offline",
        administrative_status="enabled",
        health_status="healthy",
        occupancy_status="idle",
        current_version="0.3.0",
        desired_version=None,
        protocol_version=None,
        created_at=now,
        updated_at=now,
        last_seen_at=None,
        disabled_at=None,
        local_identity="mch_1",
        machine_fingerprint="mch_1",
    )
    agents = AgentRepo(existing)
    transaction = Transaction()

    result = RegisterAgent(
        agents,
        TokenRepo("registration-secret"),
        CredentialRepo(),
        ConfigurationRepo(existing.id),
        audit_repo=None,
        outbox_repo=None,
        transaction=transaction,
    ).execute(
        "registration-secret",
        {
            "local_identity": "mch_1",
            "hostname": "MAQ65",
            "name": "certification-agent-01",
            "machine_fingerprint": "mch_1",
            "agent_version": "0.3.1",
        },
    )

    assert result.agent.id == existing.id
    assert agents.agent.name == "certification-agent-01"
    assert agents.agent.hostname == "MAQ65"
    assert agents.agent.current_version == "0.3.1"
    assert transaction.commits == 1
