from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.governance.application.dto import RetentionPolicyDTO, SecretDTO, SecretGrantDTO, SecretVersionDTO, SystemLimitDTO
from modules.governance.domain import GovernanceConflict, GovernanceResourceNotFound
from modules.governance.infrastructure.orm.models import (
    RetentionPolicyRecord,
    SecretGrantRecord,
    SecretRecord,
    SecretVersionRecord,
    SystemLimitRecord,
)


class SqlAlchemyGovernanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_secrets(self, organization_id: int | None = None) -> list[SecretDTO]:
        stmt = select(SecretRecord).order_by(SecretRecord.key)
        if organization_id is not None:
            stmt = stmt.where(SecretRecord.organization_id == organization_id)
        return [_secret_to_dto(row) for row in self.db.scalars(stmt).all()]

    def create_secret(self, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        key = _normalize_key(payload["key"])
        existing = self.db.scalar(
            select(SecretRecord).where(
                SecretRecord.organization_id.is_(payload.get("organization_id"))
                if payload.get("organization_id") is None
                else SecretRecord.organization_id == payload.get("organization_id"),
                SecretRecord.key == key,
            )
        )
        if existing is not None:
            raise GovernanceConflict("Secret key already exists in this organization.")
        secret = SecretRecord(
            id=payload.get("id") or f"sec_{uuid4().hex}",
            organization_id=payload.get("organization_id"),
            key=key,
            name=str(payload["name"]).strip(),
            description=payload.get("description"),
            status="active",
            created_by=payload.get("created_by"),
        )
        self.db.add(secret)
        self.db.flush()
        version = self._create_version(secret.id, 1, payload)
        secret.current_version_id = version.id
        self.db.add(secret)
        self.db.flush()
        return _secret_to_dto(secret), _version_to_dto(version)

    def rotate_secret(self, secret_id: str, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        secret = self.db.get(SecretRecord, secret_id)
        if secret is None:
            raise GovernanceResourceNotFound("Secret not found.")
        current_version = self.db.scalar(
            select(SecretVersionRecord.version)
            .where(SecretVersionRecord.secret_id == secret_id)
            .order_by(SecretVersionRecord.version.desc())
            .limit(1)
        )
        version = self._create_version(secret_id, int(current_version or 0) + 1, payload)
        secret.current_version_id = version.id
        secret.updated_at = utcnow()
        self.db.add(secret)
        self.db.flush()
        return _secret_to_dto(secret), _version_to_dto(version)

    def list_secret_grants(self, secret_id: str) -> list[SecretGrantDTO]:
        self._require_secret(secret_id)
        rows = self.db.scalars(
            select(SecretGrantRecord)
            .where(SecretGrantRecord.secret_id == secret_id)
            .order_by(SecretGrantRecord.created_at.desc())
        ).all()
        return [_grant_to_dto(row) for row in rows]

    def create_secret_grant(self, secret_id: str, payload: dict) -> SecretGrantDTO:
        self._require_secret(secret_id)
        row = SecretGrantRecord(
            id=payload.get("id") or f"sgr_{uuid4().hex}",
            secret_id=secret_id,
            grantee_type=str(payload["grantee_type"]),
            grantee_id=str(payload["grantee_id"]),
            permission=str(payload["permission"]),
            expires_at=payload.get("expires_at"),
        )
        self.db.add(row)
        self.db.flush()
        return _grant_to_dto(row)

    def revoke_secret_grant(self, grant_id: str) -> SecretGrantDTO:
        row = self.db.get(SecretGrantRecord, grant_id)
        if row is None:
            raise GovernanceResourceNotFound("Secret grant not found.")
        row.revoked_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return _grant_to_dto(row)

    def list_system_limits(self, organization_id: int | None = None) -> list[SystemLimitDTO]:
        stmt = select(SystemLimitRecord).order_by(SystemLimitRecord.key)
        if organization_id is not None:
            stmt = stmt.where(SystemLimitRecord.organization_id == organization_id)
        return [_limit_to_dto(row) for row in self.db.scalars(stmt).all()]

    def upsert_system_limit(self, payload: dict) -> SystemLimitDTO:
        row = self.db.scalar(
            select(SystemLimitRecord).where(
                _scope_filter(SystemLimitRecord.organization_id, payload.get("organization_id")),
                SystemLimitRecord.key == payload["key"],
            )
        )
        if row is None:
            row = SystemLimitRecord(key=payload["key"], organization_id=payload.get("organization_id"))
        row.value = int(payload["value"])
        row.unit = str(payload["unit"])
        row.description = payload.get("description")
        row.metadata_json = payload.get("metadata") or {}
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return _limit_to_dto(row)

    def list_retention_policies(self, organization_id: int | None = None) -> list[RetentionPolicyDTO]:
        stmt = select(RetentionPolicyRecord).order_by(RetentionPolicyRecord.resource_type)
        if organization_id is not None:
            stmt = stmt.where(RetentionPolicyRecord.organization_id == organization_id)
        return [_retention_to_dto(row) for row in self.db.scalars(stmt).all()]

    def upsert_retention_policy(self, payload: dict) -> RetentionPolicyDTO:
        row = self.db.scalar(
            select(RetentionPolicyRecord).where(
                _scope_filter(RetentionPolicyRecord.organization_id, payload.get("organization_id")),
                RetentionPolicyRecord.resource_type == payload["resource_type"],
            )
        )
        if row is None:
            row = RetentionPolicyRecord(resource_type=payload["resource_type"], organization_id=payload.get("organization_id"))
        row.retention_days = int(payload["retention_days"])
        row.archive_after_days = payload.get("archive_after_days")
        row.delete_after_days = payload.get("delete_after_days")
        row.legal_hold = bool(payload.get("legal_hold", False))
        row.enabled = bool(payload.get("enabled", True))
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return _retention_to_dto(row)

    def _create_version(self, secret_id: str, version: int, payload: dict) -> SecretVersionRecord:
        row = SecretVersionRecord(
            id=payload.get("version_id") or f"secv_{uuid4().hex}",
            secret_id=secret_id,
            version=version,
            encrypted_value=payload["encrypted_value"],
            encryption_key_id=payload["encryption_key_id"],
            created_by=payload.get("created_by"),
            expires_at=payload.get("expires_at"),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _require_secret(self, secret_id: str) -> SecretRecord:
        row = self.db.get(SecretRecord, secret_id)
        if row is None:
            raise GovernanceResourceNotFound("Secret not found.")
        return row


def _secret_to_dto(row: SecretRecord) -> SecretDTO:
    return SecretDTO(
        id=row.id,
        organization_id=row.organization_id,
        key=row.key,
        name=row.name,
        description=row.description,
        status=row.status,
        current_version_id=row.current_version_id,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_to_dto(row: SecretVersionRecord) -> SecretVersionDTO:
    return SecretVersionDTO(
        id=row.id,
        secret_id=row.secret_id,
        version=row.version,
        encryption_key_id=row.encryption_key_id,
        created_by=row.created_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def _grant_to_dto(row: SecretGrantRecord) -> SecretGrantDTO:
    return SecretGrantDTO(
        id=row.id,
        secret_id=row.secret_id,
        grantee_type=row.grantee_type,
        grantee_id=row.grantee_id,
        permission=row.permission,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def _limit_to_dto(row: SystemLimitRecord) -> SystemLimitDTO:
    return SystemLimitDTO(
        key=row.key,
        value=row.value,
        unit=row.unit,
        description=row.description,
        organization_id=row.organization_id,
        metadata=row.metadata_json or {},
        updated_at=row.updated_at,
    )


def _retention_to_dto(row: RetentionPolicyRecord) -> RetentionPolicyDTO:
    return RetentionPolicyDTO(
        resource_type=row.resource_type,
        retention_days=row.retention_days,
        archive_after_days=row.archive_after_days,
        delete_after_days=row.delete_after_days,
        legal_hold=row.legal_hold,
        enabled=row.enabled,
        organization_id=row.organization_id,
        updated_at=row.updated_at,
    )


def _normalize_key(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _scope_filter(column, organization_id: int | None):
    return column.is_(None) if organization_id is None else column == organization_id


def utcnow() -> datetime:
    return datetime.now(UTC)
