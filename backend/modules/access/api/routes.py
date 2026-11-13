from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.schemas import (
    AuthenticatedUserResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    RoleResponse,
    TeamCreateRequest,
    TeamResponse,
    TeamUpdateRequest,
    UserCreateRequest,
    UserPermissionsUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from modules.access.application.dto import to_payload
from modules.access.application.use_cases import (
    CreateOrganization,
    CreateTeam,
    CreateUser,
    DeleteOrganization,
    DeleteTeam,
    DeleteUser,
    GetAuthenticatedUser,
    ListOrganizations,
    ListRoles,
    ListTeams,
    ListUsers,
    UpdateOrganization,
    UpdateTeam,
    UpdateUser,
)
from modules.access.domain import AccessConflict, AccessResourceNotFound, AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters


router = APIRouter()


# POST /auth/login: em api/acesso.py desde 13/11/2026 (código por e-mail e navegador confiável).


@router.get("/auth/me", response_model=AuthenticatedUserResponse)
def me(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> AuthenticatedUserResponse:
    adapters = build_access_adapters(db)
    try:
        current = GetAuthenticatedUser(adapters.access).execute(int(user.id))
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return AuthenticatedUserResponse(**to_payload(current))


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[UserResponse]:
    adapters = build_access_adapters(db)
    try:
        sem_senha = _sem_senha(db)
        return [UserResponse(**to_payload(item), aguardando_senha=item.id in sem_senha) for item in ListUsers(adapters.access).execute(user)]
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> UserResponse:
    adapters = build_access_adapters(db)
    try:
        result = CreateUser(adapters.access, adapters.passwords, adapters.audit, adapters.transaction).execute(user, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    convite = False
    if not payload.password:  # 13/11/2026: a pessoa cria a própria senha pelo link do e-mail (48 h)
        from modules.access.api.acesso import acesso

        convite = acesso(db).convidar(result.id)
        db.commit()
    return UserResponse(**to_payload(result), aguardando_senha=not payload.password, convite_enviado=convite)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> UserResponse:
    adapters = build_access_adapters(db)
    try:
        result = UpdateUser(adapters.access, adapters.passwords, adapters.audit, adapters.transaction).execute(user, user_id, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return UserResponse(**to_payload(result))


@router.put("/users/{user_id}/permissions", response_model=UserResponse)
def update_user_permissions(
    user_id: int,
    payload: UserPermissionsUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> UserResponse:
    """Desligada em 12/11/2026: o acesso às automações de uma categoria fica no time (Times), não
    solto na pessoa. Ver ``domain/times.py`` e a migration ``b2c3d4e5f6a8``."""
    raise http_error(status.HTTP_410_GONE, "GONE",
                     "As permissões por categoria ficam nos times: ponha a pessoa num time em Times.")


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_user(user_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Response:
    adapters = build_access_adapters(db)
    try:
        DeleteUser(adapters.access, adapters.audit, adapters.transaction).execute(user, user_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(db: Session = Depends(get_db), _user: Any = Depends(get_current_user)) -> list[RoleResponse]:
    adapters = build_access_adapters(db)
    return [RoleResponse(**to_payload(item)) for item in ListRoles(adapters.access).execute()]


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[OrganizationResponse]:
    adapters = build_access_adapters(db)
    try:
        return [OrganizationResponse(**to_payload(item)) for item in ListOrganizations(adapters.access).execute(user)]
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> OrganizationResponse:
    adapters = build_access_adapters(db)
    try:
        result = CreateOrganization(adapters.access, adapters.audit, adapters.transaction).execute(user, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    return OrganizationResponse(**to_payload(result))


@router.put("/organizations/{organization_id}", response_model=OrganizationResponse)
def update_organization(organization_id: int, payload: OrganizationUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> OrganizationResponse:
    adapters = build_access_adapters(db)
    try:
        result = UpdateOrganization(adapters.access, adapters.audit, adapters.transaction).execute(user, organization_id, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return OrganizationResponse(**to_payload(result))


@router.delete("/organizations/{organization_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_organization(organization_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Response:
    adapters = build_access_adapters(db)
    try:
        DeleteOrganization(adapters.access, adapters.audit, adapters.transaction).execute(user, organization_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(organization_id: int | None = None, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[TeamResponse]:
    adapters = build_access_adapters(db)
    try:
        return [TeamResponse(**to_payload(item)) for item in ListTeams(adapters.access).execute(user, organization_id)]
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> TeamResponse:
    adapters = build_access_adapters(db)
    try:
        result = CreateTeam(adapters.access, adapters.audit, adapters.transaction).execute(user, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return TeamResponse(**to_payload(result))


@router.put("/teams/{team_id}", response_model=TeamResponse)
def update_team(team_id: int, payload: TeamUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> TeamResponse:
    adapters = build_access_adapters(db)
    try:
        result = UpdateTeam(adapters.access, adapters.audit, adapters.transaction).execute(user, team_id, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessConflict as exc:
        raise http_error(status.HTTP_409_CONFLICT, "CONFLICT", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return TeamResponse(**to_payload(result))


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_team(team_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Response:
    adapters = build_access_adapters(db)
    try:
        DeleteTeam(adapters.access, adapters.audit, adapters.transaction).execute(user, team_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.api_route("/service-accounts", methods=["GET", "POST"], include_in_schema=False)
@router.api_route("/service-accounts/{service_account_id}", methods=["PUT", "DELETE"], include_in_schema=False)
@router.api_route("/service-accounts/{service_account_id}/revoke", methods=["POST"], include_in_schema=False)
def service_accounts_antigo(service_account_id: str | None = None) -> Response:
    """Desligadas em 13/11/2026: as contas de serviço têm papel e times e ficam em
    ``/contas-de-servico`` (``api/contas_de_servico.py``)."""
    raise http_error(status.HTTP_410_GONE, "GONE", "As contas de serviço ficam em /contas-de-servico.")


def _sem_senha(db: Session) -> set[int]:
    """Quem ainda não criou a senha pelo link do convite (13/11/2026)."""
    from sqlalchemy import text

    return {i for (i,) in db.execute(text("SELECT id FROM users WHERE password_hash LIKE '!%'"))}
