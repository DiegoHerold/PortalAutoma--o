from __future__ import annotations

from typing import Any, Protocol

from modules.access.application.dto import OrganizationDTO, RoleDTO, ServiceAccountDTO, TeamDTO, UserDTO


class TransactionManager(Protocol):
    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        raise NotImplementedError

    def verify(self, password: str, password_hash: str) -> bool:
        raise NotImplementedError


class TokenIssuer(Protocol):
    def create_access_token(self, subject: str) -> str:
        raise NotImplementedError

    def decode_access_token(self, token: str) -> dict:
        raise NotImplementedError


class AccessRepository(Protocol):
    def get_user(self, user_id: int) -> UserDTO | None:
        raise NotImplementedError

    def get_user_record(self, user_id: int):
        raise NotImplementedError

    def categorias_pelos_times(self, user_id: int) -> list[Any]:
        """Permissões por categoria que os times ativos da pessoa dão."""
        raise NotImplementedError

    def get_user_by_email(self, email: str) -> UserDTO | None:
        raise NotImplementedError

    def get_user_record_by_email(self, email: str):
        raise NotImplementedError

    def list_users(self) -> list[UserDTO]:
        raise NotImplementedError

    def create_user(self, payload: dict) -> UserDTO:
        raise NotImplementedError

    def update_user(self, user_id: int, payload: dict) -> UserDTO:
        raise NotImplementedError

    def delete_user(self, user_id: int) -> None:
        raise NotImplementedError

    def set_user_permissions(self, user_id: int, permissions: list[dict]) -> UserDTO:
        raise NotImplementedError

    def user_has_requested_jobs(self, user_id: int) -> bool:
        raise NotImplementedError

    def get_automation_category_id(self, automation_id: int) -> int | None:
        raise NotImplementedError

    def mark_login(self, user_id: int) -> None:
        raise NotImplementedError

    def get_role(self, role_id: int) -> RoleDTO | None:
        raise NotImplementedError

    def get_role_by_slug(self, slug: str) -> RoleDTO | None:
        raise NotImplementedError

    def list_roles(self) -> list[RoleDTO]:
        raise NotImplementedError

    def list_permissions_for_role(self, role_id: int) -> list[str]:
        raise NotImplementedError

    def ensure_default_rbac(self) -> None:
        raise NotImplementedError

    def list_organizations(self) -> list[OrganizationDTO]:
        raise NotImplementedError

    def create_organization(self, payload: dict) -> OrganizationDTO:
        raise NotImplementedError

    def update_organization(self, organization_id: int, payload: dict) -> OrganizationDTO:
        raise NotImplementedError

    def delete_organization(self, organization_id: int) -> None:
        raise NotImplementedError

    def list_teams(self, organization_id: int | None = None) -> list[TeamDTO]:
        raise NotImplementedError

    def create_team(self, payload: dict) -> TeamDTO:
        raise NotImplementedError

    def update_team(self, team_id: int, payload: dict) -> TeamDTO:
        raise NotImplementedError

    def delete_team(self, team_id: int) -> None:
        raise NotImplementedError

    def list_service_accounts(self) -> list[ServiceAccountDTO]:
        raise NotImplementedError

    def create_service_account(self, payload: dict) -> ServiceAccountDTO:
        raise NotImplementedError

    def update_service_account(self, service_account_id: str, payload: dict) -> ServiceAccountDTO:
        raise NotImplementedError

    def delete_service_account(self, service_account_id: str) -> None:
        raise NotImplementedError

    def revoke_service_account(self, service_account_id: str) -> ServiceAccountDTO:
        raise NotImplementedError
