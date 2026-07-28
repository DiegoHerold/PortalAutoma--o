from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.governance.api.schemas import (
    AuditEntryResponse,
    AuditEventResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpsertRequest,
    SecretCreateRequest,
    SecretGrantCreateRequest,
    SecretGrantResponse,
    SecretResponse,
    SecretRotateRequest,
    SecretVersionResponse,
    SecretWithVersionResponse,
    SystemLimitResponse,
    SystemLimitUpsertRequest,
)
from modules.governance.application.dto import to_payload
from modules.governance.application.use_cases import (
    CreateSecret,
    CreateSecretGrant,
    ListAuditEvents,
    ListRetentionPolicies,
    ListSecretGrants,
    ListSecrets,
    ListSystemLimits,
    RevokeSecretGrant,
    RotateSecret,
    UpsertRetentionPolicy,
    UpsertSystemLimit,
)
from modules.governance.domain import GovernanceConflict, GovernanceResourceNotFound
from modules.governance.infrastructure.adapters import build_governance_adapters


router = APIRouter()


@router.get("/audit", response_model=list[AuditEntryResponse])
def list_audit_compat(
    actor: str | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AuditEntryResponse]:
    _ensure(db, user, "audit.read")
    adapters = build_governance_adapters(db)
    events = ListAuditEvents(adapters.audit).execute(actor=actor, resource_type=entity_type, action=action, limit=limit, offset=offset)
    return [_audit_compat(item) for item in events]


@router.get("/governance/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    actor: str | None = None,
    resource_type: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AuditEventResponse]:
    _ensure(db, user, "audit.read")
    adapters = build_governance_adapters(db)
    return [
        AuditEventResponse(**to_payload(item))
        for item in ListAuditEvents(adapters.audit).execute(actor=actor, resource_type=resource_type, action=action, limit=limit, offset=offset)
    ]


@router.get("/secrets", response_model=list[SecretResponse])
def list_secrets(
    organization_id: int | None = None,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[SecretResponse]:
    _ensure(db, user, "secret.read_metadata")
    adapters = build_governance_adapters(db)
    return [SecretResponse(**to_payload(item)) for item in ListSecrets(adapters.governance).execute(organization_id)]


@router.post("/secrets", response_model=SecretWithVersionResponse, status_code=status.HTTP_201_CREATED)
def create_secret(payload: SecretCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> SecretWithVersionResponse:
    _ensure(db, user, "secret.manage")
    adapters = build_governance_adapters(db)
    try:
        secret, version = CreateSecret(adapters.governance, adapters.cipher, adapters.audit, adapters.transaction).execute(user, payload.model_dump())
    except GovernanceConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    return SecretWithVersionResponse(secret=SecretResponse(**to_payload(secret)), version=SecretVersionResponse(**to_payload(version)))


@router.post("/secrets/{secret_id}/rotate", response_model=SecretWithVersionResponse)
def rotate_secret(secret_id: str, payload: SecretRotateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> SecretWithVersionResponse:
    _ensure(db, user, "secret.manage")
    adapters = build_governance_adapters(db)
    try:
        secret, version = RotateSecret(adapters.governance, adapters.cipher, adapters.audit, adapters.transaction).execute(user, secret_id, payload.model_dump())
    except GovernanceResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return SecretWithVersionResponse(secret=SecretResponse(**to_payload(secret)), version=SecretVersionResponse(**to_payload(version)))


@router.get("/secrets/{secret_id}/grants", response_model=list[SecretGrantResponse])
def list_secret_grants(secret_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[SecretGrantResponse]:
    _ensure(db, user, "secret.manage")
    adapters = build_governance_adapters(db)
    try:
        return [SecretGrantResponse(**to_payload(item)) for item in ListSecretGrants(adapters.governance).execute(secret_id)]
    except GovernanceResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc


@router.post("/secrets/{secret_id}/grants", response_model=SecretGrantResponse, status_code=status.HTTP_201_CREATED)
def create_secret_grant(secret_id: str, payload: SecretGrantCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> SecretGrantResponse:
    _ensure(db, user, "secret.manage")
    adapters = build_governance_adapters(db)
    try:
        grant = CreateSecretGrant(adapters.governance, adapters.audit, adapters.transaction).execute(user, secret_id, payload.model_dump())
    except GovernanceResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return SecretGrantResponse(**to_payload(grant))


@router.post("/secret-grants/{grant_id}/revoke", response_model=SecretGrantResponse)
def revoke_secret_grant(grant_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> SecretGrantResponse:
    _ensure(db, user, "secret.manage")
    adapters = build_governance_adapters(db)
    try:
        grant = RevokeSecretGrant(adapters.governance, adapters.audit, adapters.transaction).execute(user, grant_id)
    except GovernanceResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return SecretGrantResponse(**to_payload(grant))


@router.get("/governance/system-limits", response_model=list[SystemLimitResponse])
def list_system_limits(organization_id: int | None = None, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[SystemLimitResponse]:
    _ensure(db, user, "admin.system")
    adapters = build_governance_adapters(db)
    return [SystemLimitResponse(**to_payload(item)) for item in ListSystemLimits(adapters.governance).execute(organization_id)]


@router.put("/governance/system-limits/{key}", response_model=SystemLimitResponse)
def upsert_system_limit(
    key: str,
    payload: SystemLimitUpsertRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> SystemLimitResponse:
    _ensure(db, user, "admin.system")
    adapters = build_governance_adapters(db)
    data = payload.model_dump()
    data["key"] = key
    result = UpsertSystemLimit(adapters.governance, adapters.audit, adapters.transaction).execute(user, data)
    return SystemLimitResponse(**to_payload(result))


@router.get("/governance/retention-policies", response_model=list[RetentionPolicyResponse])
def list_retention_policies(organization_id: int | None = None, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[RetentionPolicyResponse]:
    _ensure(db, user, "admin.system")
    adapters = build_governance_adapters(db)
    return [RetentionPolicyResponse(**to_payload(item)) for item in ListRetentionPolicies(adapters.governance).execute(organization_id)]


@router.put("/governance/retention-policies/{resource_type}", response_model=RetentionPolicyResponse)
def upsert_retention_policy(
    resource_type: str,
    payload: RetentionPolicyUpsertRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> RetentionPolicyResponse:
    _ensure(db, user, "admin.system")
    adapters = build_governance_adapters(db)
    data = payload.model_dump()
    data["resource_type"] = resource_type
    result = UpsertRetentionPolicy(adapters.governance, adapters.audit, adapters.transaction).execute(user, data)
    return RetentionPolicyResponse(**to_payload(result))


def _ensure(db: Session, user: Any, permission: str) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_permission(user, permission)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


def _audit_compat(event) -> AuditEntryResponse:
    metadata = event.metadata or {}
    message = metadata.get("message") or metadata.get("reason")
    return AuditEntryResponse(
        id=event.id,
        actor=event.actor_id,
        actor_type=event.actor_type,
        action=event.action,
        entity_type=event.resource_type,
        entity_id=event.resource_id,
        created_at=event.occurred_at,
        before=event.before,
        after=event.after,
        message=str(message) if message is not None else None,
    )
