from __future__ import annotations

from datetime import datetime, timedelta

from modules.fleet.domain.agent import Agent, AgentAdministrativeStatus, AgentConnectivityStatus
from modules.fleet.domain.capability import AgentCapability, CapabilityStatus
from modules.fleet.domain.configuration import AgentConfiguration
from modules.fleet.domain.pool import AgentPool
from modules.fleet.domain.registration import AgentCredential, AgentRegistrationToken


def test_agent_uses_multidimensional_states() -> None:
    agent = Agent(id="agt_1", name="A1", hostname="host-a")

    agent.mark_connected(datetime.utcnow(), "1.0")
    agent.set_draining()

    assert agent.connectivity_status == AgentConnectivityStatus.ONLINE
    assert agent.administrative_status == AgentAdministrativeStatus.DRAINING


def test_registration_token_is_single_use() -> None:
    now = datetime.utcnow()
    token = AgentRegistrationToken(
        id="art_1",
        token_hash="hash",
        status="active",
        expires_at=now + timedelta(minutes=5),
        created_by="1",
        created_at=now,
    )

    token.ensure_usable(now)
    token.mark_used("agt_1", now)

    assert token.status == "used"
    assert token.used_by_agent_id == "agt_1"


def test_credential_revoke_blocks_usage() -> None:
    now = datetime.utcnow()
    credential = AgentCredential(
        id="acr_1",
        agent_id="agt_1",
        credential_type="bearer_token",
        public_identifier="pub",
        secret_hash="hash",
        status="active",
        issued_at=now,
    )

    credential.revoke(now)

    assert credential.status == "revoked"
    assert credential.revoked_at == now


def test_capability_key_is_typed() -> None:
    capability = AgentCapability(
        key="browser.chrome",
        status=CapabilityStatus.AVAILABLE,
        observed_at=datetime.utcnow(),
        attributes={"interactive_required": True},
    )

    assert capability.key == "browser.chrome"
    assert not capability.is_expired(datetime.utcnow())


def test_pool_available_capacity_is_derived() -> None:
    pool = AgentPool(
        agent_id="agt_1",
        pool_type="background",
        recommended_total=3,
        administrator_total=2,
        effective_total=2,
        used=1,
        reserved=1,
        observed_at=datetime.utcnow(),
    )

    assert pool.available == 0


def test_configuration_separates_admin_policy_from_observed_capacity() -> None:
    configuration = AgentConfiguration(agent_id="agt_1", administrator_pool_limits={"background": 1})

    assert configuration.administrator_pool_limits["background"] == 1
    assert configuration.heartbeat_interval_seconds == 30
