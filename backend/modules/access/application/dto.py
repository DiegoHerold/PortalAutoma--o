from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RoleDTO:
    id: int
    name: str
    slug: str
    description: str | None = None
    permissions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CategoryPermissionDTO:
    id: int | None
    category_id: int
    category_name: str | None
    can_view: bool
    can_execute: bool
    can_create: bool
    can_edit: bool
    can_delete: bool
    can_approve: bool


@dataclass(frozen=True)
class UserDTO:
    id: int
    name: str
    email: str
    status: str
    is_active: bool
    role: RoleDTO
    organization_id: int | None = None
    category_permissions: list[CategoryPermissionDTO] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    disabled_at: datetime | None = None


@dataclass(frozen=True)
class AuthenticatedUserDTO:
    id: int
    email: str
    name: str
    role: str
    role_id: int
    organization_id: int | None
    permissions: list[CategoryPermissionDTO]
    rbac_permissions: list[str]


@dataclass(frozen=True)
class TokenDTO:
    access_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class OrganizationDTO:
    id: int
    key: str
    name: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class TeamDTO:
    id: int
    organization_id: int
    key: str
    name: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ServiceAccountDTO:
    id: str
    organization_id: int | None
    name: str
    status: str
    permissions: list[str]
    created_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class CreatedServiceAccountDTO:
    service_account: ServiceAccountDTO
    credential: str


def to_payload(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value

