from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"
    ARCHIVED = "archived"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class TeamStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class RoleSlug(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


class ServiceAccountStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"
    ARCHIVED = "archived"


ADMIN_PERMISSION = "*"

