from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import column, exists, select, table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from modules.access.application.dto import (
    CategoryPermissionDTO,
    OrganizationDTO,
    RoleDTO,
    ServiceAccountDTO,
    TeamDTO,
    UserDTO,
)
from modules.access.domain import ADMIN_PERMISSION, INITIAL_PERMISSIONS, AccessConflict, AccessResourceNotFound, RoleSlug, UserStatus, normalize_email
from modules.access.infrastructure.orm.models import (
    AccessOrganizationRecord,
    AccessRoleRecord,
    AccessTeamRecord,
    AccessUserCategoryPermissionRecord,
    AccessUserRecord,
    PermissionRecord,
    RolePermissionRecord,
    ServiceAccountRecord,
)


class SqlAlchemyTransactionManager:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyAccessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_record(self, user_id: int) -> AccessUserRecord | None:
        return self.db.scalar(_user_query().where(AccessUserRecord.id == user_id))

    def get_user_record_by_email(self, email: str) -> AccessUserRecord | None:
        return self.db.scalar(_user_query().where(AccessUserRecord.email == normalize_email(email)))

    def categorias_pelos_times(self, user_id: int) -> list[CategoryPermissionDTO]:
        from modules.access.infrastructure.repositories.sqlalchemy_times import SqlAlchemyTimes

        return SqlAlchemyTimes(self.db).categorias_pelos_times(user_id)

    def get_user(self, user_id: int) -> UserDTO | None:
        row = self.get_user_record(user_id)
        return _user_to_dto(row, self.list_permissions_for_role(row.role_id)) if row else None

    def e_usuario_tecnico(self, user_id: int) -> bool:
        return self.db.scalar(select(ServiceAccountRecord.id).where(ServiceAccountRecord.user_id == user_id)) is not None

    def get_user_by_email(self, email: str) -> UserDTO | None:
        row = self.get_user_record_by_email(email)
        return _user_to_dto(row, self.list_permissions_for_role(row.role_id)) if row else None

    def list_users(self) -> list[UserDTO]:
        # Os usuários técnicos das contas de serviço ficam em Contas de serviço, não em Usuários.
        tecnicos = select(ServiceAccountRecord.user_id).where(ServiceAccountRecord.user_id.is_not(None))
        rows = self.db.scalars(_user_query().where(AccessUserRecord.id.not_in(tecnicos)).order_by(AccessUserRecord.name)).unique().all()
        return [_user_to_dto(row, self.list_permissions_for_role(row.role_id)) for row in rows]

    def create_user(self, payload: dict) -> UserDTO:
        now = utcnow()
        row = AccessUserRecord(
            name=str(payload["name"]).strip(),
            email=normalize_email(payload["email"]),
            password_hash=payload["password_hash"],
            role_id=int(payload["role_id"]),
            organization_id=payload.get("organization_id"),
            status=str(payload.get("status") or (UserStatus.ACTIVE if payload.get("is_active", True) else UserStatus.DISABLED)),
            is_active=bool(payload.get("is_active", True)),
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.flush()
        return self.get_user(row.id) or _user_to_dto(row, [])

    def update_user(self, user_id: int, payload: dict) -> UserDTO:
        row = self.get_user_record(user_id)
        if row is None:
            raise ValueError("User not found.")
        for key in ["name", "email", "password_hash", "role_id", "organization_id"]:
            if key in payload:
                setattr(row, key, normalize_email(payload[key]) if key == "email" else payload[key])
        if "is_active" in payload:
            row.is_active = bool(payload["is_active"])
            row.status = UserStatus.ACTIVE if row.is_active else UserStatus.DISABLED
            row.disabled_at = None if row.is_active else row.disabled_at or utcnow()
        if "status" in payload:
            row.status = str(payload["status"])
            row.is_active = row.status == UserStatus.ACTIVE
            row.disabled_at = None if row.is_active else row.disabled_at or utcnow()
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return self.get_user(user_id) or _user_to_dto(row, [])

    def delete_user(self, user_id: int) -> None:
        row = self.get_user_record(user_id)
        if row is not None:
            self.db.delete(row)
            self.db.flush()

    def set_user_permissions(self, user_id: int, permissions: list[dict]) -> UserDTO:
        existing = {
            permission.category_id: permission
            for permission in self.db.scalars(
                select(AccessUserCategoryPermissionRecord).where(AccessUserCategoryPermissionRecord.user_id == user_id)
            ).all()
        }
        for item in permissions:
            category_id = int(item["category_id"])
            row = existing.get(category_id)
            if row is None:
                row = AccessUserCategoryPermissionRecord(user_id=user_id, category_id=category_id)
                self.db.add(row)
            row.can_view = bool(item.get("can_view", False))
            row.can_execute = bool(item.get("can_execute", False))
            row.can_create = bool(item.get("can_create", False))
            row.can_edit = bool(item.get("can_edit", False))
            row.can_delete = bool(item.get("can_delete", False))
            row.can_approve = bool(item.get("can_approve", False))
        self.db.flush()
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("User not found.")
        return user

    def user_has_requested_jobs(self, user_id: int) -> bool:
        jobs = table("jobs", column("requested_by_user_id"))
        return bool(self.db.scalar(select(exists().where(jobs.c.requested_by_user_id == user_id))))

    def get_automation_category_id(self, automation_id: int) -> int | None:
        automations = table("automations", column("id"), column("category_id"))
        return self.db.scalar(select(automations.c.category_id).where(automations.c.id == automation_id))

    def mark_login(self, user_id: int) -> None:
        row = self.db.get(AccessUserRecord, user_id)
        if row is not None:
            row.last_login_at = utcnow()
            row.updated_at = utcnow()
            self.db.add(row)
            self.db.flush()

    def get_role(self, role_id: int) -> RoleDTO | None:
        row = self.db.get(AccessRoleRecord, role_id)
        return _role_to_dto(row, self.list_permissions_for_role(role_id)) if row else None

    def get_role_by_slug(self, slug: str) -> RoleDTO | None:
        row = self.db.scalar(select(AccessRoleRecord).where(AccessRoleRecord.slug == str(slug)))
        return _role_to_dto(row, self.list_permissions_for_role(row.id)) if row else None

    def list_roles(self) -> list[RoleDTO]:
        rows = self.db.scalars(select(AccessRoleRecord).order_by(AccessRoleRecord.name)).all()
        return [_role_to_dto(row, self.list_permissions_for_role(row.id)) for row in rows]

    def list_permissions_for_role(self, role_id: int) -> list[str]:
        from modules.access.domain.funcionalidades import permissoes_efetivas

        role = self.db.get(AccessRoleRecord, role_id)
        if role and role.slug == RoleSlug.ADMIN:
            return [ADMIN_PERMISSION]
        gravadas = self.db.scalars(
            select(RolePermissionRecord.permission_key)
            .where(RolePermissionRecord.role_id == role_id)
            .order_by(RolePermissionRecord.permission_key)
        ).all()
        if role is None:
            return list(gravadas)
        # A tabela de funcionalidades do papel (ou, no papel de antes, o que ela deduz) manda.
        return permissoes_efetivas(role.slug, gravadas, role.abas, role.funcionalidades)

    def ensure_default_rbac(self) -> None:
        for permission in INITIAL_PERMISSIONS:
            if self.db.get(PermissionRecord, permission) is None:
                self.db.add(PermissionRecord(key=permission, description=None))
        self.db.flush()
        role_permissions = {
            RoleSlug.MANAGER: [p for p in INITIAL_PERMISSIONS if not p.startswith("admin.") and p != "secret.manage"],
            RoleSlug.OPERATOR: [
                "automation.read",
                "execution.read",
                "execution.create",
                "execution.cancel",
                "flow.read",
                "flow.execute",
                "schedule.read",
                "schedule.trigger",
                "artifact.read",
                "artifact.download",
                "agent.read",
            ],
            RoleSlug.VIEWER: [
                "automation.read",
                "execution.read",
                "flow.read",
                "schedule.read",
                "artifact.read",
                "agent.read",
            ],
        }
        for role_slug, permissions in role_permissions.items():
            role = self.db.scalar(select(AccessRoleRecord).where(AccessRoleRecord.slug == role_slug))
            if role is None:
                continue
            # O que está GRAVADO (e não o que vale): aba ou funcionalidade desligada tira permissões do
            # que vale, e pedir de novo as gravadas violaria a chave única (12/11/2026).
            existing = set(self.db.scalars(select(RolePermissionRecord.permission_key)
                                           .where(RolePermissionRecord.role_id == role.id)).all())
            for permission in permissions:
                if permission not in existing:
                    self.db.add(RolePermissionRecord(role_id=role.id, permission_key=permission))
        for role in self.db.scalars(select(AccessRoleRecord)).all():
            role.is_system = role.slug in {item.value for item in RoleSlug}
            role.status = role.status or "active"
            self.db.add(role)
        self.db.flush()

    def list_organizations(self) -> list[OrganizationDTO]:
        rows = self.db.scalars(select(AccessOrganizationRecord).order_by(AccessOrganizationRecord.name)).all()
        return [_organization_to_dto(row) for row in rows]

    def create_organization(self, payload: dict) -> OrganizationDTO:
        key = str(payload["key"]).strip().lower()
        if self.db.scalar(select(AccessOrganizationRecord.id).where(AccessOrganizationRecord.key == key)) is not None:
            raise AccessConflict("Organization key already exists.")
        row = AccessOrganizationRecord(
            key=key,
            name=str(payload["name"]).strip(),
            status=str(payload.get("status") or "active"),
        )
        self.db.add(row)
        self.db.flush()
        return _organization_to_dto(row)

    def update_organization(self, organization_id: int, payload: dict) -> OrganizationDTO:
        row = self.db.get(AccessOrganizationRecord, organization_id)
        if row is None:
            raise AccessResourceNotFound("Organization not found.")
        key = str(payload["key"]).strip().lower()
        duplicate = self.db.scalar(select(AccessOrganizationRecord.id).where(AccessOrganizationRecord.key == key, AccessOrganizationRecord.id != organization_id))
        if duplicate is not None:
            raise AccessConflict("Organization key already exists.")
        row.key, row.name, row.status, row.updated_at = key, str(payload["name"]).strip(), str(payload["status"]), utcnow()
        self.db.add(row)
        self.db.flush()
        return _organization_to_dto(row)

    def delete_organization(self, organization_id: int) -> None:
        row = self.db.get(AccessOrganizationRecord, organization_id)
        if row is None:
            raise AccessResourceNotFound("Organization not found.")
        if self.db.scalar(select(exists().where(AccessTeamRecord.organization_id == organization_id))) or self.db.scalar(select(exists().where(AccessUserRecord.organization_id == organization_id))) or self.db.scalar(select(exists().where(ServiceAccountRecord.organization_id == organization_id))):
            raise AccessConflict("Organization still has linked users, teams, or service accounts.")
        governance_resources = (
            table("secrets", column("organization_id")),
            table("system_limits", column("organization_id")),
            table("retention_policies", column("organization_id")),
        )
        if any(self.db.scalar(select(exists().where(resource.c.organization_id == organization_id))) for resource in governance_resources):
            raise AccessConflict("Organization still has linked governance settings.")
        self.db.delete(row)
        self.db.flush()

    def list_teams(self, organization_id: int | None = None) -> list[TeamDTO]:
        stmt = select(AccessTeamRecord).order_by(AccessTeamRecord.name)
        if organization_id is not None:
            stmt = stmt.where(AccessTeamRecord.organization_id == organization_id)
        return [_team_to_dto(row) for row in self.db.scalars(stmt).all()]

    def create_team(self, payload: dict) -> TeamDTO:
        organization_id = int(payload["organization_id"])
        if self.db.get(AccessOrganizationRecord, organization_id) is None:
            raise AccessResourceNotFound("Selected organization was not found.")
        key = str(payload["key"]).strip().lower()
        if self.db.scalar(select(AccessTeamRecord.id).where(AccessTeamRecord.organization_id == organization_id, AccessTeamRecord.key == key)) is not None:
            raise AccessConflict("Team key already exists in this organization.")
        row = AccessTeamRecord(
            organization_id=organization_id,
            key=key,
            name=str(payload["name"]).strip(),
            status=str(payload.get("status") or "active"),
        )
        self.db.add(row)
        self.db.flush()
        return _team_to_dto(row)

    def update_team(self, team_id: int, payload: dict) -> TeamDTO:
        row = self.db.get(AccessTeamRecord, team_id)
        if row is None:
            raise AccessResourceNotFound("Team not found.")
        organization_id = int(payload["organization_id"])
        if self.db.get(AccessOrganizationRecord, organization_id) is None:
            raise AccessResourceNotFound("Selected organization was not found.")
        key = str(payload["key"]).strip().lower()
        duplicate = self.db.scalar(select(AccessTeamRecord.id).where(AccessTeamRecord.organization_id == organization_id, AccessTeamRecord.key == key, AccessTeamRecord.id != team_id))
        if duplicate is not None:
            raise AccessConflict("Team key already exists in this organization.")
        row.organization_id, row.key, row.name, row.status, row.updated_at = organization_id, key, str(payload["name"]).strip(), str(payload["status"]), utcnow()
        self.db.add(row)
        self.db.flush()
        return _team_to_dto(row)

    def delete_team(self, team_id: int) -> None:
        row = self.db.get(AccessTeamRecord, team_id)
        if row is None:
            raise AccessResourceNotFound("Team not found.")
        self.db.delete(row)
        self.db.flush()

    def list_service_accounts(self) -> list[ServiceAccountDTO]:
        rows = self.db.scalars(select(ServiceAccountRecord).order_by(ServiceAccountRecord.created_at.desc())).all()
        return [_service_account_to_dto(row) for row in rows]

    def create_service_account(self, payload: dict) -> ServiceAccountDTO:
        row = ServiceAccountRecord(
            id=payload.get("id") or f"sa_{uuid4().hex}",
            organization_id=payload.get("organization_id"),
            name=str(payload["name"]).strip(),
            status=str(payload.get("status") or "active"),
            credential_hash=payload["credential_hash"],
            permissions=list(payload.get("permissions") or []),
            expires_at=payload.get("expires_at"),
        )
        self.db.add(row)
        self.db.flush()
        return _service_account_to_dto(row)

    def update_service_account(self, service_account_id: str, payload: dict) -> ServiceAccountDTO:
        row = self.db.get(ServiceAccountRecord, service_account_id)
        if row is None:
            raise AccessResourceNotFound("Service account not found.")
        organization_id = payload.get("organization_id")
        if organization_id is not None and self.db.get(AccessOrganizationRecord, int(organization_id)) is None:
            raise AccessResourceNotFound("Selected organization was not found.")
        row.name = str(payload["name"]).strip()
        row.organization_id = organization_id
        row.permissions = list(payload.get("permissions") or [])
        row.expires_at = payload.get("expires_at")
        self.db.add(row)
        self.db.flush()
        return _service_account_to_dto(row)

    def delete_service_account(self, service_account_id: str) -> None:
        row = self.db.get(ServiceAccountRecord, service_account_id)
        if row is None:
            raise AccessResourceNotFound("Service account not found.")
        self.db.delete(row)
        self.db.flush()

    def revoke_service_account(self, service_account_id: str) -> ServiceAccountDTO:
        row = self.db.get(ServiceAccountRecord, service_account_id)
        if row is None:
            raise ValueError("ServiceAccount not found.")
        row.status = "revoked"
        row.revoked_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return _service_account_to_dto(row)


def _user_query():
    return select(AccessUserRecord).options(selectinload(AccessUserRecord.category_permissions))


def _role_to_dto(row: AccessRoleRecord, permissions: list[str]) -> RoleDTO:
    return RoleDTO(id=row.id, name=row.name, slug=row.slug, description=row.description, permissions=permissions)


def _category_permission_to_dto(row: AccessUserCategoryPermissionRecord) -> CategoryPermissionDTO:
    return CategoryPermissionDTO(
        id=row.id,
        category_id=row.category_id,
        category_name=row.category.name if row.category else None,
        can_view=row.can_view,
        can_execute=row.can_execute,
        can_create=row.can_create,
        can_edit=row.can_edit,
        can_delete=row.can_delete,
        can_approve=row.can_approve,
    )


def _user_to_dto(row: AccessUserRecord, permissions: list[str]) -> UserDTO:
    status = row.status or (UserStatus.ACTIVE if row.is_active else UserStatus.DISABLED)
    return UserDTO(
        id=row.id,
        name=row.name,
        email=row.email,
        status=str(status),
        is_active=row.is_active and status == UserStatus.ACTIVE,
        role=_role_to_dto(row.role, permissions),
        organization_id=row.organization_id,
        category_permissions=[_category_permission_to_dto(item) for item in row.category_permissions],
        permissions=permissions,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_login_at=row.last_login_at,
        disabled_at=row.disabled_at,
    )


def _organization_to_dto(row: AccessOrganizationRecord) -> OrganizationDTO:
    return OrganizationDTO(id=row.id, key=row.key, name=row.name, status=row.status, created_at=row.created_at, updated_at=row.updated_at)


def _team_to_dto(row: AccessTeamRecord) -> TeamDTO:
    return TeamDTO(id=row.id, organization_id=row.organization_id, key=row.key, name=row.name, status=row.status, created_at=row.created_at, updated_at=row.updated_at)


def _service_account_to_dto(row: ServiceAccountRecord) -> ServiceAccountDTO:
    return ServiceAccountDTO(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        status=row.status,
        permissions=list(row.permissions or []),
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


def commit_or_raise(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
