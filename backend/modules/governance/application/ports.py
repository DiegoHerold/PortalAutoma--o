from __future__ import annotations

from typing import Protocol

from modules.governance.application.dto import RetentionPolicyDTO, SecretDTO, SecretGrantDTO, SecretVersionDTO, SystemLimitDTO
from modules.governance.domain.audit import AuditEvent


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent:
        raise NotImplementedError


class TransactionManager(Protocol):
    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class SecretCipher(Protocol):
    key_id: str

    def encrypt(self, value: str) -> str:
        raise NotImplementedError

    def decrypt(self, value: str) -> str:
        raise NotImplementedError


class GovernanceRepository(Protocol):
    def list_secrets(self, organization_id: int | None = None) -> list[SecretDTO]:
        raise NotImplementedError

    def create_secret(self, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        raise NotImplementedError

    def rotate_secret(self, secret_id: str, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        raise NotImplementedError

    def list_secret_grants(self, secret_id: str) -> list[SecretGrantDTO]:
        raise NotImplementedError

    def create_secret_grant(self, secret_id: str, payload: dict) -> SecretGrantDTO:
        raise NotImplementedError

    def revoke_secret_grant(self, grant_id: str) -> SecretGrantDTO:
        raise NotImplementedError

    def list_system_limits(self, organization_id: int | None = None) -> list[SystemLimitDTO]:
        raise NotImplementedError

    def upsert_system_limit(self, payload: dict) -> SystemLimitDTO:
        raise NotImplementedError

    def list_retention_policies(self, organization_id: int | None = None) -> list[RetentionPolicyDTO]:
        raise NotImplementedError

    def upsert_retention_policy(self, payload: dict) -> RetentionPolicyDTO:
        raise NotImplementedError
