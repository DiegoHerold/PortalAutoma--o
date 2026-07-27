from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
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
)
from modules.fleet.application.dto import ActorDTO
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
from modules.fleet.domain.errors import FleetError
from modules.fleet.infrastructure.adapters import build_fleet_adapters

router = APIRouter()


@router.post("/agents/registration-tokens", status_code=status.HTTP_201_CREATED)
def create_registration_token(
    payload: CreateRegistrationTokenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    try:
        credential = RevokeAgentCredential(adapters.credentials, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, payload.credential_id, _actor(user))
    except FleetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _json(credential)


@router.get("/agents")
def list_agents(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(agent) for agent in ListAgents(adapters.agents).execute()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> dict[str, Any]:
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
    user: User = Depends(get_current_user),
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
        saved = adapters.agents.save(agent.__class__(**{**asdict(agent), "name": payload.name, "updated_at": datetime.utcnow()}))
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
def enable_agent(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(EnableAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/disable")
def disable_agent(agent_id: str, payload: DisableAgentRequest = Body(default_factory=DisableAgentRequest), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(DisableAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.reason))


@router.post("/agents/{agent_id}/drain")
def drain_agent(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(DrainAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/resume")
def resume_agent(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(ResumeAgent(adapters.agents, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/maintenance")
def maintenance_agent(agent_id: str, payload: MaintenanceRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(SetAgentMaintenance(adapters.agents, adapters.configurations, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.enabled))


@router.post("/agents/{agent_id}/diagnostics")
def request_diagnostics(agent_id: str, payload: AgentCommandRequest = Body(default_factory=AgentCommandRequest), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentDiagnostic(adapters.agents, adapters.commands, adapters.diagnostics, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.payload))


@router.post("/agents/{agent_id}/capabilities/refresh")
def request_capability_refresh(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentCapabilitiesRefresh(adapters.agents, adapters.commands, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user)))


@router.post("/agents/{agent_id}/update")
def request_update(agent_id: str, payload: AgentUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(RequestAgentUpdate(adapters.agents, adapters.commands, adapters.audit, adapters.outbox, adapters.transaction).execute(agent_id, _actor(user), payload.desired_version))


@router.get("/agents/{agent_id}/instances")
def list_agent_instances(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(item) for item in GetAgentInstances(adapters.instances).execute(agent_id)]


@router.get("/agents/{agent_id}/capabilities")
def list_agent_capabilities(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    adapters = build_fleet_adapters(db)
    return [_json(item) for item in GetAgentCapabilities(adapters.capabilities).execute(agent_id)]


@router.get("/agents/{agent_id}/capacity")
def get_agent_capacity(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    return _json(GetAgentCapacity(adapters.pools, adapters.snapshots).execute(agent_id))


@router.get("/agents/{agent_id}/history")
def get_agent_history(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    history = GetAgentHistory(adapters.instances).execute(agent_id)
    history["diagnostics"] = adapters.diagnostics.list_for_agent(agent_id)
    return _json(history)


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id))


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
