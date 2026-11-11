from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.fleet.application.dto import ActorDTO, AgentConfigurationDTO, AgentDTO, AgentPoolDTO
from modules.fleet.application.ports import AgentConfigurationRepository, AgentPoolRepository, FleetOutbox
from modules.fleet.domain import states
from modules.governance.application.ports import AuditEventRepository
from modules.governance.domain.audit import AuditEvent


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def audit(
    audit_repo: AuditEventRepository | None,
    actor: ActorDTO,
    action: str,
    resource_type: str,
    resource_id: str,
    after: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repo is None:
        return
    audit_repo.append(
        AuditEvent(
            id=str(uuid4()),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
            metadata=metadata or {},
            ip=actor.ip,
            user_agent=actor.user_agent,
            occurred_at=utcnow(),
        )
    )


def outbox(outbox_repo: FleetOutbox | None, event_type: str, agent_id: str, payload: dict[str, Any]) -> None:
    if outbox_repo is not None:
        outbox_repo.append_event(event_type, agent_id, payload)


def default_configuration(agent_id: str) -> AgentConfigurationDTO:
    return AgentConfigurationDTO(
        agent_id=agent_id,
        heartbeat_interval_seconds=30,
        stale_after_seconds=90,
        offline_after_seconds=180,
        administrator_pool_limits={pool: None for pool in states.DEFAULT_AGENT_POOLS},
        enabled_pools=list(states.DEFAULT_AGENT_POOLS),
        allowlist_capabilities=[],
        maintenance=False,
        desired_version=None,
        restrictions={},
        updated_at=utcnow(),
    )


def ensure_configuration(repo: AgentConfigurationRepository, agent_id: str) -> AgentConfigurationDTO:
    existing = repo.get(agent_id)
    if existing is not None:
        return existing
    return repo.save(default_configuration(agent_id))


def calculate_pool(agent_id: str, pool_type: str, observed_at: datetime, payload: dict[str, Any], configuration: AgentConfigurationDTO, revision: int) -> AgentPoolDTO:
    recommended = _int_or_none(payload.get("total") if "total" in payload else payload.get("recommended_total"))
    administrator_total = configuration.administrator_pool_limits.get(pool_type)
    if administrator_total is None:
        effective_total = recommended or 0
    else:
        effective_total = min(recommended or administrator_total, administrator_total)
    used = max(0, int(payload.get("used") or 0))
    reserved = max(0, int(payload.get("reserved") or 0))
    available = max(0, effective_total - used - reserved)
    return AgentPoolDTO(
        agent_id=agent_id,
        pool_type=pool_type,
        recommended_total=recommended,
        administrator_total=administrator_total,
        effective_total=max(0, effective_total),
        used=used,
        reserved=reserved,
        available=available,
        observed_at=observed_at,
        revision=max(1, revision),
    )


def occupancy_from_pools(pools: list[AgentPoolDTO]) -> str:
    total = sum(pool.effective_total for pool in pools)
    used = sum(pool.used + pool.reserved for pool in pools)
    if total <= 0 or used <= 0:
        return "idle"
    if used >= total:
        return "saturated"
    return "busy"


def apply_agent_update(agent: AgentDTO, **changes: Any) -> AgentDTO:
    return replace(agent, updated_at=utcnow(), **changes)


def parse_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return _em_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            pass
    return fallback or utcnow()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _em_utc(valor: datetime) -> datetime:
    """Texto sem fuso é UTC; com fuso, convertido para UTC (o banco guarda timestamptz)."""
    return valor.astimezone(UTC) if valor.tzinfo is not None else valor.replace(tzinfo=UTC)
