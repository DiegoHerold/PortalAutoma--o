from __future__ import annotations

from modules.fleet.application.dto import AgentDTO, AgentInstanceDTO
from modules.fleet.application.use_cases._shared import default_configuration, utcnow
from modules.fleet.application.use_cases.presence import RecordAgentHeartbeat


class AgentRepo:
    def __init__(self, agent: AgentDTO) -> None:
        self.agent = agent

    def get(self, agent_id: str) -> AgentDTO | None:
        return self.agent if self.agent.id == agent_id else None

    def save(self, agent: AgentDTO) -> AgentDTO:
        self.agent = agent
        return agent


class InstanceRepo:
    def __init__(self, instance: AgentInstanceDTO) -> None:
        self.instance = instance

    def get_current(self, agent_id: str) -> AgentInstanceDTO | None:
        return self.instance if self.instance.agent_id == agent_id and self.instance.disconnected_at is None else None

    def save(self, instance: AgentInstanceDTO) -> AgentInstanceDTO:
        self.instance = instance
        return instance


class SnapshotRepo:
    def add(self, snapshot):
        return snapshot


class SessionRepo:
    def add(self, session):
        return session


class PoolRepo:
    def __init__(self) -> None:
        self.current = []

    def replace_current(self, agent_id: str, pools: list):
        self.current = pools
        return pools

    def list_current(self, agent_id: str):
        return self.current


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


def test_heartbeat_accepts_agent_capacity_payload_as_pool_snapshot() -> None:
    now = utcnow()
    agent = AgentDTO(
        id="agt_capacity",
        name="Agent Capacity",
        hostname="host",
        enabled=True,
        connectivity_status="online",
        administrative_status="enabled",
        health_status="healthy",
        occupancy_status="idle",
        current_version="0.3.0",
        desired_version=None,
        protocol_version="1.0",
        created_at=now,
        updated_at=now,
        last_seen_at=now,
        disabled_at=None,
    )
    instance = AgentInstanceDTO(
        id="agi_capacity",
        agent_id=agent.id,
        process_started_at=now,
        connected_at=now,
        last_seen_at=now,
        disconnected_at=None,
        shutdown_reason=None,
        agent_version="0.3.0",
        negotiated_protocol_version="1.0",
        connection_id="conn",
        created_at=now,
    )
    pools = PoolRepo()
    transaction = Transaction()

    RecordAgentHeartbeat(
        AgentRepo(agent),
        InstanceRepo(instance),
        SnapshotRepo(),
        SessionRepo(),
        pools,
        ConfigurationRepo(agent.id),
        outbox_repo=None,
        transaction=transaction,
    ).execute(
        agent.id,
        instance.id,
        {
            "observed_at": now.isoformat(),
            "capacity": {
                "background": {"total": 2, "used": 0, "reserved": 0},
                "browser": {"total": 1, "used": 0, "reserved": 0},
                "interactive": {"total": 0, "used": 0, "reserved": 0},
            },
        },
    )

    by_type = {pool.pool_type: pool for pool in pools.current}
    assert by_type["background"].effective_total == 2
    assert by_type["background"].available == 2
    assert by_type["browser"].available == 1
    assert transaction.commits == 1
