from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import ensure_permission
from modules.access.api.dependencies import get_current_user
from modules.fleet.api.schemas import (
    AgentCommandRequest,
    AgentConfigurationPatchRequest,
    AgentPatchRequest,
    AgentUpdateRequest,
    CreateRegistrationTokenRequest,
    DisableAgentRequest,
    MaintenanceRequest,
    RegisterAgentRequest,
    RevokeCredentialRequest,
    RotateCredentialResponse,
    StartAgentInstanceRequest,
    WorkerCreateRequest,
    WorkerResponse,
    WorkerUpdateRequest,
)
from modules.fleet.application.dto import ActorDTO, AgentDTO
from modules.fleet.application.use_cases import (
    CreateAgentRegistrationToken,
    DisableAgent,
    DrainAgent,
    EnableAgent,
    GetAgent,
    GetAgentCapabilities,
    GetAgentCapacity,
    GetAgentHistory,
    GetAgentInstances,
    ListAgents,
    RegisterAgent,
    RequestAgentCapabilitiesRefresh,
    RequestAgentDiagnostic,
    RequestAgentUpdate,
    ResumeAgent,
    RevokeAgentCredential,
    RevokeAgentRegistrationToken,
    RotateAgentCredential,
    SetAgentMaintenance,
    StartAgentInstance,
    UpdateAgentConfiguration,
    ValidateAgentCredential,
)
from modules.fleet.application.use_cases._shared import default_configuration
from modules.fleet.domain.errors import FleetError
from modules.fleet.domain.value_objects import generate_agent_id
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.fleet.infrastructure.orm.models import FleetWorkerRecord

router = APIRouter()


@router.get("/workers/installer-config")
def installer_config(_user: Any = Depends(get_current_user)) -> dict[str, str]:
    settings = get_settings()
    base = settings.backend_public_url.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return {
        "central_api_url": f"{base}/api",
        "central_websocket_url": f"{ws_base}/api/v1/agent-gateway/connect",
    }


@router.get("/workers", response_model=list[WorkerResponse])
def list_workers(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[WorkerResponse]:
    ensure_permission(db, user, "agent.read")
    adapters = build_fleet_adapters(db)
    agents = adapters.agents.list()
    if not agents:
        agents = [_ensure_agent_for_worker(db, worker) for worker in db.scalars(select(FleetWorkerRecord).order_by(FleetWorkerRecord.name)).all()]
        adapters.transaction.commit()
    return [_worker_response(db, agent) for agent in agents]


@router.get("/workers/{worker_id}", response_model=WorkerResponse)
def get_worker(worker_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> WorkerResponse:
    ensure_permission(db, user, "agent.read")
    agent = _get_agent_by_worker_id(db, worker_id)
    return _worker_response(db, agent)


@router.post("/workers", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    payload: WorkerCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> WorkerResponse:
    ensure_permission(db, user, "agent.manage")
    now = datetime.now(UTC)
    adapters = build_fleet_adapters(db)
    created = adapters.agents.add(
        AgentDTO(
            id=payload.agent_id or generate_agent_id(),
            worker_id=None,
            name=payload.name,
            hostname=payload.hostname,
            enabled=payload.is_active,
            connectivity_status=_compat_connectivity(payload.status),
            administrative_status="enabled" if payload.is_active else "disabled",
            health_status="healthy",
            occupancy_status="busy" if payload.status == "busy" else "idle",
            current_version=payload.agent_version,
            desired_version=payload.desired_version,
            protocol_version=None,
            created_at=now,
            updated_at=now,
            last_seen_at=None,
            disabled_at=None if payload.is_active else now,
            local_identity=payload.machine_id,
            machine_fingerprint=payload.machine_id,
        )
    )
    adapters.configurations.save(default_configuration(created.id))
    adapters.transaction.commit()
    return _worker_response(db, created)


@router.put("/workers/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: int,
    payload: WorkerUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> WorkerResponse:
    ensure_permission(db, user, "agent.manage")
    adapters = build_fleet_adapters(db)
    agent = _get_agent_by_worker_id(db, worker_id)
    updated = adapters.agents.save(
        AgentDTO(
            **{
                **asdict(agent),
                "name": payload.name,
                "hostname": payload.hostname,
                "enabled": payload.is_active,
                "connectivity_status": _compat_connectivity(payload.status),
                "administrative_status": "enabled" if payload.is_active else "disabled",
                "occupancy_status": "busy" if payload.status == "busy" else agent.occupancy_status,
                "current_version": payload.agent_version or agent.current_version,
                "desired_version": payload.desired_version or agent.desired_version,
                "local_identity": payload.machine_id or agent.local_identity,
                "machine_fingerprint": payload.machine_id or agent.machine_fingerprint,
                "updated_at": datetime.now(UTC),
            }
        )
    )
    adapters.transaction.commit()
    return _worker_response(db, updated)


@router.delete("/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_worker(worker_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    ensure_permission(db, user, "agent.disable")
    adapters = build_fleet_adapters(db)
    agent = _get_agent_by_worker_id(db, worker_id)
    DisableAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(
        agent.id,
        actor=_actor(user),
        reason="disabled through /workers compatibility API",
    )


@router.post("/agents/registration-tokens", status_code=status.HTTP_201_CREATED)
def create_registration_token(
    payload: CreateRegistrationTokenRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    result = CreateAgentRegistrationToken(adapters.registration_tokens, adapters.audit, adapters.outbox, adapters.transaction).execute(
        _actor(user),
        expires_in_seconds=payload.expires_in_seconds,
        metadata=payload.metadata,
    )
    data = _json(result)
    data["registration_token"] = data.pop("token")
    return data


@router.post("/agents/registration-tokens/{token_id}/revoke")
def revoke_registration_token(
    token_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    try:
        result = RevokeAgentRegistrationToken(adapters.registration_tokens, adapters.audit, adapters.outbox, adapters.transaction).execute(token_id, _actor(user))
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _json(result)


@router.post("/agents/register", status_code=status.HTTP_201_CREATED)
def register_agent(payload: RegisterAgentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    try:
        result = RegisterAgent(
            adapters.agents,
            adapters.registration_tokens,
            adapters.credentials,
            adapters.configurations,
            adapters.audit,
            adapters.outbox,
            adapters.transaction,
        ).execute(payload.registration_token, payload.model_dump(exclude={"registration_token"}))
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    data = _json(result)
    credential = data["credential"]
    credential["bearer_token"] = f"{credential['public_identifier']}:{credential['secret']}"
    return data


@router.post("/agents/{agent_id}/credentials/rotate", response_model=RotateCredentialResponse)
def rotate_credential(
    agent_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> RotateCredentialResponse:
    adapters = build_fleet_adapters(db)
    try:
        credential = RotateAgentCredential(adapters.credentials, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user))
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if credential.secret is None:
        raise HTTPException(status_code=500, detail="Credential secret was not issued.")
    return RotateCredentialResponse(
        id=credential.id,
        agent_id=credential.agent_id,
        public_identifier=credential.public_identifier,
        secret=credential.secret,
        bearer_token=f"{credential.public_identifier}:{credential.secret}",
    )


@router.post("/agents/{agent_id}/credentials/revoke")
def revoke_credential(
    agent_id: str,
    payload: RevokeCredentialRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    try:
        credential = RevokeAgentCredential(adapters.credentials, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, payload.credential_id, _actor(user))
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _json(credential)


@router.get("/agents")
def list_agents(db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(agent) for agent in ListAgents(adapters.agents).execute()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    try:
        return _json(GetAgent(adapters.agents).execute(agent_id))
    except FleetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/agents/{agent_id}")
def patch_agent(
    agent_id: str,
    payload: AgentPatchRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    if payload.configuration is not None or payload.desired_version is not None:
        config_payload = payload.configuration.model_dump(exclude_none=True) if payload.configuration else {}
        if payload.desired_version:
            config_payload["desired_version"] = payload.desired_version
        result = UpdateAgentConfiguration(adapters.agents, adapters.configurations, adapters.commands, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), config_payload)
        return _json(result)
    if payload.name:
        agent = adapters.agents.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        saved = adapters.agents.save(agent.__class__(**{**asdict(agent), "name": payload.name, "updated_at": datetime.now(UTC)}))
        adapters.transaction.commit()
        return _json(saved)
    return get_agent(agent_id, db, user)


@router.post("/agents/{agent_id}/instances", status_code=status.HTTP_201_CREATED)
def start_agent_instance(
    agent_id: str,
    payload: StartAgentInstanceRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    _validate_agent_bearer(adapters, authorization, agent_id)
    try:
        instance = StartAgentInstance(adapters.agents, adapters.instances, adapters.audit, adapters.outbox, adapters.transaction).execute(
            agent_id,
            payload.agent_version,
            process_started_at=payload.process_started_at,
        )
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _json(instance)


@router.post("/agents/{agent_id}/enable")
def enable_agent(agent_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(EnableAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/disable")
def disable_agent(agent_id: str, payload: DisableAgentRequest = Body(default_factory=DisableAgentRequest), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(DisableAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.reason))


@router.post("/agents/{agent_id}/drain")
def drain_agent(agent_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(DrainAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/resume")
def resume_agent(agent_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(ResumeAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/maintenance")
def maintenance_agent(agent_id: str, payload: MaintenanceRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(SetAgentMaintenance(adapters.agents, adapters.configurations, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.enabled))


@router.post("/agents/{agent_id}/diagnostics")
def request_diagnostics(agent_id: str, payload: AgentCommandRequest = Body(default_factory=AgentCommandRequest), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentDiagnostic(adapters.agents, adapters.commands, adapters.diagnostics, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.payload))


@router.post("/agents/{agent_id}/capabilities/refresh")
def request_capability_refresh(agent_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentCapabilitiesRefresh(adapters.agents, adapters.commands, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/update")
def request_update(agent_id: str, payload: AgentUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentUpdate(adapters.agents, adapters.commands, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.desired_version))


@router.get("/agents/{agent_id}/instances")
def list_agent_instances(agent_id: str, db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(item) for item in GetAgentInstances(adapters.instances).execute(agent_id)]


@router.get("/agents/{agent_id}/capabilities")
def list_agent_capabilities(agent_id: str, db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(item) for item in GetAgentCapabilities(adapters.capabilities).execute(agent_id)]


@router.get("/agents/{agent_id}/capacity")
def get_agent_capacity(agent_id: str, db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(GetAgentCapacity(adapters.pools, adapters.snapshots).execute(agent_id))


@router.get("/agents/{agent_id}/history")
def get_agent_history(agent_id: str, db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    history = GetAgentHistory(adapters.instances).execute(agent_id)
    history["diagnostics"] = adapters.diagnostics.list_for_agent(agent_id)
    return _json(history)


def _actor(user: Any) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id))


def _get_agent_by_worker_id(db: Session, worker_id: int) -> AgentDTO:
    adapters = build_fleet_adapters(db)
    agent = adapters.agents.get_by_worker_id(worker_id)
    if agent is not None:
        return agent
    worker = db.get(FleetWorkerRecord, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found.")
    created = _ensure_agent_for_worker(db, worker)
    adapters.transaction.commit()
    return created


def _ensure_agent_for_worker(db: Session, worker: FleetWorkerRecord) -> AgentDTO:
    adapters = build_fleet_adapters(db)
    existing = adapters.agents.get(worker.agent_id) if worker.agent_id else None
    if existing is not None:
        return existing
    now = datetime.now(UTC)
    agent_id = worker.agent_id or f"agt_worker_{worker.id}"
    if not worker.agent_id:
        worker.agent_id = agent_id
        db.add(worker)
        db.flush()
    return adapters.agents.add(
        AgentDTO(
            id=agent_id,
            worker_id=worker.id,
            name=worker.name,
            hostname=worker.hostname,
            enabled=worker.is_active,
            connectivity_status=_compat_connectivity(worker.status),
            administrative_status="enabled" if worker.is_active and worker.status != "disabled" else "disabled",
            health_status="healthy",
            occupancy_status="busy" if worker.status == "busy" else "idle",
            current_version=worker.agent_version,
            desired_version=None,
            protocol_version=None,
            created_at=getattr(worker, "created_at", None) or now,
            updated_at=getattr(worker, "updated_at", None) or now,
            last_seen_at=worker.last_heartbeat_at,
            disabled_at=None if worker.is_active else now,
            local_identity=worker.machine_id,
            machine_fingerprint=worker.machine_id,
        )
    )


def _worker_response(db: Session, agent: AgentDTO) -> WorkerResponse:
    worker_id = agent.worker_id
    if worker_id is None:
        adapters = build_fleet_adapters(db)
        saved = adapters.agents.save(agent)
        db.flush()
        worker_id = saved.worker_id
        agent = saved
    pools_total = sum((pool.get("effective_total") or 0) for pool in agent.pools.values())
    pools_used = sum((pool.get("used") or 0) for pool in agent.pools.values())
    return WorkerResponse(
        id=worker_id or 0,
        name=agent.name,
        hostname=agent.hostname,
        ip_address=None,
        agent_id=agent.id,
        machine_id=agent.local_identity,
        agent_version=agent.current_version,
        os=None,
        architecture=None,
        capabilities_json=[],
        last_payload_json={
            "agent": {
                "connectivity_status": agent.connectivity_status,
                "administrative_status": agent.administrative_status,
                "health_status": agent.health_status,
                "occupancy_status": agent.occupancy_status,
                "interactive_session": agent.interactive_session,
                "pools": agent.pools,
            }
        },
        status=agent.connectivity_status,
        connectivity_status=agent.connectivity_status,
        administrative_status=agent.administrative_status,
        health_status=agent.health_status,
        occupancy_status=agent.occupancy_status,
        desired_version=agent.desired_version,
        cpu_percentage=agent.cpu_percentage,
        memory_percentage=agent.memory_percentage,
        disk_free_mb=agent.disk_free_mb,
        interactive_session=agent.interactive_session,
        pools=agent.pools,
        alerts=agent.alerts,
        max_concurrency=max(1, pools_total or _legacy_worker_max(db, agent.worker_id)),
        last_heartbeat_at=agent.last_seen_at.isoformat() if agent.last_seen_at else None,
        is_active=agent.enabled and agent.administrative_status != "disabled",
        active_jobs=pools_used,
    )


def _legacy_worker_max(db: Session, worker_id: int | None) -> int:
    if worker_id is None:
        return 1
    worker = db.get(FleetWorkerRecord, worker_id)
    return worker.max_concurrency if worker else 1


def _compat_connectivity(value: str | None) -> str:
    if value in {"online", "stale", "disconnected", "offline"}:
        return value
    if value == "busy":
        return "online"
    if value == "disabled":
        return "offline"
    return "offline"


def _validate_agent_bearer(adapters, authorization: str | None, expected_agent_id: str):
    public_identifier, secret = _parse_bearer(authorization)
    if not public_identifier or not secret:
        raise HTTPException(status_code=401, detail="Agent credential is required.")
    try:
        agent = ValidateAgentCredential(adapters.agents, adapters.credentials, adapters.transaction).execute(public_identifier, secret)
    except FleetError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if agent.id != expected_agent_id:
        raise HTTPException(status_code=403, detail="Credential does not belong to this Agent.")
    return agent


def _parse_bearer(authorization: str | None) -> tuple[str | None, str | None]:
    if not authorization:
        return None, None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or ":" not in value:
        return None, None
    public_identifier, _, secret = value.partition(":")
    return public_identifier.strip(), secret.strip()


def _json(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _json(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
