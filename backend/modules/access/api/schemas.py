from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class CategoryPermissionResponse(BaseModel):
    id: int | None = None
    category_id: int
    category_name: str | None = None
    can_view: bool
    can_execute: bool
    can_create: bool
    can_edit: bool
    can_delete: bool
    can_approve: bool


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    # Sem senha (o normal desde 13/11/2026): a pessoa recebe o convite e cria a dela.
    password: str | None = None
    role_id: int = Field(gt=0)
    is_active: bool = True
    organization_id: int | None = None


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    role_id: int = Field(gt=0)
    is_active: bool = True
    password: str | None = None
    organization_id: int | None = None


class UserPermissionsUpdateRequest(BaseModel):
    permissions: list[CategoryPermissionResponse]


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    status: str = "active"
    is_active: bool
    role: RoleResponse
    organization_id: int | None = None
    category_permissions: list[CategoryPermissionResponse] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    aguardando_senha: bool = False  # convidada, ainda sem senha (13/11/2026)
    convite_enviado: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    disabled_at: datetime | None = None


class AuthenticatedUserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    role_id: int
    organization_id: int | None = None
    permissions: list[CategoryPermissionResponse] = Field(default_factory=list)
    rbac_permissions: list[str] = Field(default_factory=list)


class OrganizationCreateRequest(BaseModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = "active"


class OrganizationUpdateRequest(OrganizationCreateRequest):
    pass


class OrganizationResponse(BaseModel):
    id: int
    key: str
    name: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TeamCreateRequest(BaseModel):
    organization_id: int = Field(gt=0)
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = "active"


class TeamUpdateRequest(TeamCreateRequest):
    pass


class TeamResponse(BaseModel):
    id: int
    organization_id: int
    key: str
    name: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
