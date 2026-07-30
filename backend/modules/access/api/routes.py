from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.schemas import (
    AuthenticatedUserResponse,
    CreatedServiceAccountResponse,
    LoginRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    RoleResponse,
    ServiceAccountCreateRequest,
    ServiceAccountResponse,
    ServiceAccountUpdateRequest,
    TeamCreateRequest,
    TeamResponse,
    TeamUpdateRequest,
    TokenResponse,
    UserCreateRequest,
    UserPermissionsUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from modules.access.application.dto import to_payload
from modules.access.application.use_cases import (
    CreateOrganization,
    CreateServiceAccount,
    CreateTeam,
    CreateUser,
    DeleteOrganization,
    DeleteServiceAccount,
    DeleteTeam,
    DeleteUser,
    GetAuthenticatedUser,
    ListOrganizations,
    ListRoles,
    ListServiceAccounts,
    ListTeams,
    ListUsers,
    LoginUser,
    RevokeServiceAccount,
    UpdateOrganization,
    UpdateServiceAccount,
    UpdateTeam,
    UpdateUser,
    UpdateUserPermissions,
)
from modules.access.domain import AccessConflict, AccessResourceNotFound, AuthenticationFailed, AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters


router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    adapters = build_access_adapters(db)
    try:
        token = LoginUser(adapters.access, adapters.passwords, adapters.tokens, adapters.audit, adapters.transaction).execute(
            payload.email,
            payload.password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationFailed as exc:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_REQUIRED", str(exc)) from exc
    return TokenResponse(**to_payload(token))


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
        return [UserResponse(**to_payload(item)) for item in ListUsers(adapters.access).execute(user)]
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
    return UserResponse(**to_payload(result))


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> UserResponse:
    adapters = build_access_adapters(db)
    try:
        result = UpdateUser(adapters.access, adapters.passwords, adapters.audit, adapters.transaction).execute(user, user_id, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
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
    adapters = build_access_adapters(db)
    try:
        result = UpdateUserPermissions(adapters.access, adapters.audit, adapters.transaction).execute(
            user,
            user_id,
            [item.model_dump() for item in payload.permissions],
        )
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return UserResponse(**to_payload(result))


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


@router.get("/service-accounts", response_model=list[ServiceAccountResponse])
def list_service_accounts(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[ServiceAccountResponse]:
    adapters = build_access_adapters(db)
    try:
        return [ServiceAccountResponse(**to_payload(item)) for item in ListServiceAccounts(adapters.access).execute(user)]
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


@router.post("/service-accounts", response_model=CreatedServiceAccountResponse, status_code=status.HTTP_201_CREATED)
def create_service_account(payload: ServiceAccountCreateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> CreatedServiceAccountResponse:
    adapters = build_access_adapters(db)
    try:
        result = CreateServiceAccount(adapters.access, adapters.passwords, adapters.audit, adapters.transaction).execute(user, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    return CreatedServiceAccountResponse(**to_payload(result))


@router.put("/service-accounts/{service_account_id}", response_model=ServiceAccountResponse)
def update_service_account(service_account_id: str, payload: ServiceAccountUpdateRequest, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ServiceAccountResponse:
    adapters = build_access_adapters(db)
    try:
        result = UpdateServiceAccount(adapters.access, adapters.audit, adapters.transaction).execute(user, service_account_id, payload.model_dump())
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return ServiceAccountResponse(**to_payload(result))


@router.delete("/service-accounts/{service_account_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_service_account(service_account_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Response:
    adapters = build_access_adapters(db)
    try:
        DeleteServiceAccount(adapters.access, adapters.audit, adapters.transaction).execute(user, service_account_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/service-accounts/{service_account_id}/revoke", response_model=ServiceAccountResponse)
def revoke_service_account(service_account_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ServiceAccountResponse:
    adapters = build_access_adapters(db)
    try:
        result = RevokeServiceAccount(adapters.access, adapters.audit, adapters.transaction).execute(user, service_account_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
    except ValueError as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return ServiceAccountResponse(**to_payload(result))
