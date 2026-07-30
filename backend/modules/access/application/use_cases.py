from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.access.application.dto import AuthenticatedUserDTO, CreatedServiceAccountDTO, ServiceAccountDTO, TokenDTO, UserDTO
from modules.access.application.ports import AccessRepository, PasswordHasher, TokenIssuer, TransactionManager
from modules.access.domain import AccessConflict, AccessResourceNotFound, AuthenticationFailed, AuthorizationDenied, RoleSlug, UserStatus, normalize_email
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository


ADMIN_LIKE_ROLES = {RoleSlug.ADMIN.value, RoleSlug.MANAGER.value}


class PermissionChecker:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def has_permission(self, user: Any, permission: str, *, category_id: int | None = None) -> bool:
        role_slug = _role_slug(user)
        if role_slug == RoleSlug.ADMIN.value:
            return True
        rbac_permissions = set(_rbac_permissions(user))
        role_id = getattr(user, "role_id", None) or getattr(getattr(user, "role", None), "id", None)
        if role_id is not None:
            rbac_permissions.update(self.access.list_permissions_for_role(int(role_id)))
        if permission in rbac_permissions:
            return True
        if category_id is not None:
            return _legacy_category_allowed(user, category_id, permission)
        return False

    def ensure_permission(self, user: Any, permission: str, *, category_id: int | None = None) -> None:
        if not self.has_permission(user, permission, category_id=category_id):
            raise AuthorizationDenied(f"Permission denied: {permission}.")

    def ensure_admin_or_manager(self, user: Any) -> None:
        if _role_slug(user) not in ADMIN_LIKE_ROLES:
            raise AuthorizationDenied("This action requires elevated privileges.")

    def ensure_category_action(self, user: Any, category_id: int, action: str) -> None:
        permission = _legacy_action_to_permission(action)
        self.ensure_permission(user, permission, category_id=category_id)

    def ensure_automation_action(self, user: Any, automation_id: int, action: str) -> int:
        category_id = self.access.get_automation_category_id(automation_id)
        if category_id is None:
            raise AccessResourceNotFound("Automation not found.")
        self.ensure_category_action(user, category_id, action)
        return int(category_id)


class LoginUser:
    def __init__(self, access: AccessRepository, passwords: PasswordHasher, tokens: TokenIssuer, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.passwords = passwords
        self.tokens = tokens
        self.audit = audit
        self.transaction = transaction

    def execute(self, email: str, password: str, *, ip: str | None = None, user_agent: str | None = None) -> TokenDTO:
        normalized = normalize_email(email)
        user = self.access.get_user_by_email(normalized)
        if user is None or not user.is_active:
            self._audit("login_failed", normalized, "unknown", ip, user_agent, {"reason": "invalid_user"})
            self.transaction.commit()
            raise AuthenticationFailed("Invalid email or password.")
        record = self.access.get_user_record_by_email(normalized)
        password_hash = getattr(record, "password_hash", None)
        if not password_hash or not self.passwords.verify(password, password_hash):
            self._audit("login_failed", normalized, str(user.id), ip, user_agent, {"reason": "invalid_password"})
            self.transaction.commit()
            raise AuthenticationFailed("Invalid email or password.")
        self.access.mark_login(user.id)
        self._audit("login_succeeded", normalized, str(user.id), ip, user_agent, None)
        self.transaction.commit()
        return TokenDTO(access_token=self.tokens.create_access_token(str(user.id)))

    def _audit(self, action: str, actor_id: str, resource_id: str, ip: str | None, user_agent: str | None, metadata: dict | None) -> None:
        self.audit.append(
            AuditEvent(
                id=new_id("aud"),
                actor_type="user",
                actor_id=actor_id,
                action=action,
                resource_type="user",
                resource_id=resource_id,
                metadata=metadata or {},
                ip=ip,
                user_agent=user_agent,
                occurred_at=utcnow(),
            )
        )


class AuthenticateToken:
    def __init__(self, access: AccessRepository, tokens: TokenIssuer) -> None:
        self.access = access
        self.tokens = tokens

    def execute(self, token: str) -> Any:
        payload = self.tokens.decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise AuthenticationFailed("Could not validate credentials.")
        user = self.access.get_user_record(int(subject))
        if user is None or not bool(getattr(user, "is_active", False)) or getattr(user, "status", "active") != UserStatus.ACTIVE:
            raise AuthenticationFailed("Could not validate credentials.")
        return user


class GetAuthenticatedUser:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self, user_id: int) -> AuthenticatedUserDTO:
        user = self.access.get_user(user_id)
        if user is None:
            raise AccessResourceNotFound("User not found.")
        return AuthenticatedUserDTO(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.slug,
            role_id=user.role.id,
            organization_id=user.organization_id,
            permissions=user.category_permissions,
            rbac_permissions=user.permissions,
        )


class ListUsers:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self, actor: Any) -> list[UserDTO]:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        return self.access.list_users()


class CreateUser:
    def __init__(self, access: AccessRepository, passwords: PasswordHasher, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.passwords = passwords
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]) -> UserDTO:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        email = normalize_email(payload["email"])
        if self.access.get_user_by_email(email) is not None:
            raise AccessConflict("User email already exists.")
        if self.access.get_role(int(payload["role_id"])) is None:
            raise AccessResourceNotFound("Selected role was not found.")
        created = self.access.create_user(
            {
                "name": str(payload["name"]).strip(),
                "email": email,
                "password_hash": self.passwords.hash(payload["password"]),
                "role_id": int(payload["role_id"]),
                "is_active": bool(payload.get("is_active", True)),
                "organization_id": payload.get("organization_id"),
            }
        )
        _audit(self.audit, actor, "user_created", "user", str(created.id), after={"email": created.email})
        self.transaction.commit()
        return created


class UpdateUser:
    def __init__(self, access: AccessRepository, passwords: PasswordHasher, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.passwords = passwords
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, user_id: int, payload: dict[str, Any]) -> UserDTO:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        current = self.access.get_user(user_id)
        if current is None:
            raise AccessResourceNotFound("User not found.")
        if self.access.get_role(int(payload["role_id"])) is None:
            raise AccessResourceNotFound("Selected role was not found.")
        update = {
            "name": str(payload["name"]).strip(),
            "email": normalize_email(payload["email"]),
            "role_id": int(payload["role_id"]),
            "is_active": bool(payload.get("is_active", True)),
            "organization_id": payload.get("organization_id", current.organization_id),
        }
        if payload.get("password"):
            update["password_hash"] = self.passwords.hash(payload["password"])
        updated = self.access.update_user(user_id, update)
        _audit(self.audit, actor, "user_updated", "user", str(updated.id), before={"email": current.email}, after={"email": updated.email})
        self.transaction.commit()
        return updated


class UpdateUserPermissions:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, user_id: int, permissions: list[dict[str, Any]]) -> UserDTO:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        if self.access.get_user(user_id) is None:
            raise AccessResourceNotFound("User not found.")
        updated = self.access.set_user_permissions(user_id, permissions)
        _audit(self.audit, actor, "user_permissions_updated", "user", str(user_id), after={"permission_count": len(permissions)})
        self.transaction.commit()
        return updated


class DeleteUser:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, user_id: int) -> None:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        actor_id = int(getattr(actor, "id"))
        if actor_id == user_id:
            raise AccessConflict("You cannot delete your own user.")
        current = self.access.get_user(user_id)
        if current is None:
            raise AccessResourceNotFound("User not found.")
        _audit(self.audit, actor, "user_deleted", "user", str(user_id), before={"email": current.email})
        if self.access.user_has_requested_jobs(user_id):
            self.access.update_user(user_id, {"is_active": False, "status": UserStatus.DISABLED})
        else:
            self.access.delete_user(user_id)
        self.transaction.commit()


class ListRoles:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self) -> list:
        return self.access.list_roles()


class BootstrapAccessDefaults:
    def __init__(self, access: AccessRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.transaction = transaction

    def execute(self) -> None:
        self.access.ensure_default_rbac()
        if not self.access.list_organizations():
            self.access.create_organization({"key": "default", "name": "Default Organization"})
        self.transaction.commit()


class ListOrganizations:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self, actor: Any) -> list:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        return self.access.list_organizations()


class CreateOrganization:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]):
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        created = self.access.create_organization(payload)
        _audit(self.audit, actor, "organization_created", "organization", str(created.id), after={"key": created.key})
        self.transaction.commit()
        return created


class UpdateOrganization:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, organization_id: int, payload: dict[str, Any]):
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        updated = self.access.update_organization(organization_id, payload)
        _audit(self.audit, actor, "organization_updated", "organization", str(updated.id), after={"key": updated.key, "status": updated.status})
        self.transaction.commit()
        return updated


class DeleteOrganization:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, organization_id: int) -> None:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        self.access.delete_organization(organization_id)
        _audit(self.audit, actor, "organization_deleted", "organization", str(organization_id))
        self.transaction.commit()


class ListTeams:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self, actor: Any, organization_id: int | None = None) -> list:
        PermissionChecker(self.access).ensure_admin_or_manager(actor)
        return self.access.list_teams(organization_id)


class CreateTeam:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]):
        PermissionChecker(self.access).ensure_permission(actor, "admin.users")
        created = self.access.create_team(payload)
        _audit(self.audit, actor, "team_created", "team", str(created.id), after={"key": created.key})
        self.transaction.commit()
        return created


class UpdateTeam:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, team_id: int, payload: dict[str, Any]):
        PermissionChecker(self.access).ensure_permission(actor, "admin.users")
        updated = self.access.update_team(team_id, payload)
        _audit(self.audit, actor, "team_updated", "team", str(updated.id), after={"key": updated.key, "organization_id": updated.organization_id, "status": updated.status})
        self.transaction.commit()
        return updated


class DeleteTeam:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, team_id: int) -> None:
        PermissionChecker(self.access).ensure_permission(actor, "admin.users")
        self.access.delete_team(team_id)
        _audit(self.audit, actor, "team_deleted", "team", str(team_id))
        self.transaction.commit()


class ListServiceAccounts:
    def __init__(self, access: AccessRepository) -> None:
        self.access = access

    def execute(self, actor: Any) -> list[ServiceAccountDTO]:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        return self.access.list_service_accounts()


class CreateServiceAccount:
    def __init__(self, access: AccessRepository, passwords: PasswordHasher, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.passwords = passwords
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]) -> CreatedServiceAccountDTO:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        credential = f"psa_{secrets.token_urlsafe(32)}"
        created = self.access.create_service_account(
            {
                "organization_id": payload.get("organization_id"),
                "name": payload["name"],
                "credential_hash": self.passwords.hash(credential),
                "permissions": payload.get("permissions") or [],
                "expires_at": payload.get("expires_at"),
            }
        )
        _audit(self.audit, actor, "service_account_created", "service_account", created.id, after={"permission_count": len(created.permissions)})
        self.transaction.commit()
        return CreatedServiceAccountDTO(service_account=created, credential=credential)


class RevokeServiceAccount:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, service_account_id: str) -> ServiceAccountDTO:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        revoked = self.access.revoke_service_account(service_account_id)
        _audit(self.audit, actor, "service_account_revoked", "service_account", service_account_id)
        self.transaction.commit()
        return revoked


class UpdateServiceAccount:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, service_account_id: str, payload: dict[str, Any]) -> ServiceAccountDTO:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        updated = self.access.update_service_account(service_account_id, payload)
        _audit(self.audit, actor, "service_account_updated", "service_account", service_account_id, after={"permission_count": len(updated.permissions), "status": updated.status})
        self.transaction.commit()
        return updated


class DeleteServiceAccount:
    def __init__(self, access: AccessRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.access = access
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, service_account_id: str) -> None:
        PermissionChecker(self.access).ensure_permission(actor, "admin.system")
        self.access.delete_service_account(service_account_id)
        _audit(self.audit, actor, "service_account_deleted", "service_account", service_account_id)
        self.transaction.commit()


def _role_slug(user: Any) -> str | None:
    role = getattr(user, "role", None)
    if isinstance(role, str):
        return role
    return getattr(role, "slug", None)


def _rbac_permissions(user: Any) -> list[str]:
    value = getattr(user, "rbac_permissions", None) or getattr(user, "permissions", None) or []
    return [str(item) for item in value if isinstance(item, str)]


def _legacy_category_allowed(user: Any, category_id: int, permission: str) -> bool:
    action = _permission_to_legacy_action(permission)
    if action is None:
        return False
    for item in getattr(user, "category_permissions", []) or []:
        if int(getattr(item, "category_id", 0)) == int(category_id) and bool(getattr(item, action, False)):
            return True
    return False


def _legacy_action_to_permission(action: str) -> str:
    return {
        "can_view": "automation.read",
        "can_execute": "execution.create",
        "can_create": "automation.create",
        "can_edit": "automation.update",
        "can_delete": "automation.update",
        "can_approve": "automation.publish",
    }.get(action, action)


def _permission_to_legacy_action(permission: str) -> str | None:
    return {
        "automation.read": "can_view",
        "runtime.read": "can_view",
        "agent.read": "can_view",
        "execution.read": "can_view",
        "flow.read": "can_view",
        "schedule.read": "can_view",
        "artifact.read": "can_view",
        "artifact.download": "can_view",
        "execution.create": "can_execute",
        "flow.execute": "can_execute",
        "schedule.trigger": "can_execute",
        "execution.cancel": "can_execute",
        "automation.create": "can_create",
        "flow.create": "can_create",
        "schedule.create": "can_create",
        "automation.update": "can_edit",
        "flow.update": "can_edit",
        "schedule.update": "can_edit",
        "automation.publish": "can_approve",
        "flow.publish": "can_approve",
    }.get(permission)


def _audit(audit: SqlAlchemyAuditEventRepository, actor: Any, action: str, resource_type: str, resource_id: str, before: dict | None = None, after: dict | None = None) -> None:
    audit.append(
        AuditEvent(
            id=new_id("aud"),
            actor_type="user",
            actor_id=str(getattr(actor, "id", "")) or None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
            occurred_at=utcnow(),
        )
    )


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(UTC)
