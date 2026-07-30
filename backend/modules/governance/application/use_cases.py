from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.governance.application.dto import AuditEventDTO, RetentionPolicyDTO, SecretDTO, SecretGrantDTO, SecretVersionDTO, SystemLimitDTO
from modules.governance.application.ports import GovernanceRepository, SecretCipher, TransactionManager
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository


DEFAULT_SYSTEM_LIMITS = (
    {"key": "package.max_size_mb", "value": 200, "unit": "mb", "description": "Maximum automation package upload size."},
    {"key": "artifact.max_size_mb", "value": 200, "unit": "mb", "description": "Maximum individual artifact size."},
    {"key": "agent.max_registered", "value": 100, "unit": "count", "description": "Maximum registered agents."},
    {"key": "execution.max_concurrent", "value": 20, "unit": "count", "description": "Maximum concurrent executions."},
    {"key": "schedule.min_interval_seconds", "value": 60, "unit": "seconds", "description": "Minimum recurring schedule interval."},
    {"key": "flow.max_nodes", "value": 100, "unit": "count", "description": "Maximum nodes in a flow."},
    {"key": "execution.max_timeout_seconds", "value": 14400, "unit": "seconds", "description": "Maximum execution timeout."},
    {"key": "execution.max_retries", "value": 3, "unit": "count", "description": "Maximum retry attempts."},
    {"key": "realtime.max_sse_connections", "value": 250, "unit": "count", "description": "Maximum SSE connections."},
    {"key": "gateway.max_message_bytes", "value": 65536, "unit": "bytes", "description": "Maximum gateway message size."},
)

DEFAULT_RETENTION_POLICIES = (
    {"resource_type": "ExecutionEvent", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
    {"resource_type": "ExecutionLog", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
    {"resource_type": "ExecutionMetric", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
    {"resource_type": "Artifact", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 365, "legal_hold": False, "enabled": True},
    {"resource_type": "AgentResourceSnapshot", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
    {"resource_type": "AuditEvent", "retention_days": 365, "archive_after_days": None, "delete_after_days": None, "legal_hold": True, "enabled": True},
    {"resource_type": "InboxMessage", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
    {"resource_type": "OutboxMessage", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
    {"resource_type": "AgentCommand", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
    {"resource_type": "Diagnostic", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
)


class ListAuditEvents:
    def __init__(self, audit: SqlAlchemyAuditEventRepository) -> None:
        self.audit = audit

    def execute(
        self,
        *,
        actor: str | None = None,
        query: str | None = None,
        actor_type: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventDTO]:
        return [
            AuditEventDTO(
                id=row.id,
                organization_id=row.organization_id,
                actor_type=row.actor_type,
                actor_id=row.actor_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                before=row.before,
                after=row.after,
                metadata=row.metadata_json or {},
                correlation_id=row.correlation_id,
                ip=row.ip,
                user_agent=row.user_agent,
                occurred_at=row.occurred_at,
            )
            for row in self.audit.list(
                actor=actor,
                query=query,
                actor_type=actor_type,
                resource_type=resource_type,
                action=action,
                occurred_from=occurred_from,
                occurred_until=occurred_until,
                limit=limit,
                offset=offset,
            )
        ]


class ListSecrets:
    def __init__(self, governance: GovernanceRepository) -> None:
        self.governance = governance

    def execute(self, organization_id: int | None = None) -> list[SecretDTO]:
        return self.governance.list_secrets(organization_id)


class CreateSecret:
    def __init__(self, governance: GovernanceRepository, cipher: SecretCipher, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.cipher = cipher
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]) -> tuple[SecretDTO, SecretVersionDTO]:
        secret, version = self.governance.create_secret(
            {
                "key": payload["key"],
                "name": payload["name"],
                "description": payload.get("description"),
                "organization_id": payload.get("organization_id"),
                "encrypted_value": self.cipher.encrypt(payload["value"]),
                "encryption_key_id": self.cipher.key_id,
                "expires_at": payload.get("expires_at"),
                "created_by": _actor_id(actor),
            }
        )
        _audit(self.audit, actor, "secret_created", "secret", secret.id, after={"key": secret.key, "version": version.version})
        self.transaction.commit()
        return secret, version


class RotateSecret:
    def __init__(self, governance: GovernanceRepository, cipher: SecretCipher, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.cipher = cipher
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, secret_id: str, payload: dict[str, Any]) -> tuple[SecretDTO, SecretVersionDTO]:
        secret, version = self.governance.rotate_secret(
            secret_id,
            {
                "encrypted_value": self.cipher.encrypt(payload["value"]),
                "encryption_key_id": self.cipher.key_id,
                "expires_at": payload.get("expires_at"),
                "created_by": _actor_id(actor),
            },
        )
        _audit(self.audit, actor, "secret_rotated", "secret", secret.id, after={"version": version.version})
        self.transaction.commit()
        return secret, version


class ListSecretGrants:
    def __init__(self, governance: GovernanceRepository) -> None:
        self.governance = governance

    def execute(self, secret_id: str) -> list[SecretGrantDTO]:
        return self.governance.list_secret_grants(secret_id)


class CreateSecretGrant:
    def __init__(self, governance: GovernanceRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, secret_id: str, payload: dict[str, Any]) -> SecretGrantDTO:
        grant = self.governance.create_secret_grant(secret_id, payload)
        _audit(
            self.audit,
            actor,
            "secret_grant_created",
            "secret_grant",
            grant.id,
            after={"secret_id": secret_id, "grantee_type": grant.grantee_type, "permission": grant.permission},
        )
        self.transaction.commit()
        return grant


class RevokeSecretGrant:
    def __init__(self, governance: GovernanceRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, grant_id: str) -> SecretGrantDTO:
        grant = self.governance.revoke_secret_grant(grant_id)
        _audit(self.audit, actor, "secret_grant_revoked", "secret_grant", grant.id, after={"secret_id": grant.secret_id})
        self.transaction.commit()
        return grant


class ListSystemLimits:
    def __init__(self, governance: GovernanceRepository) -> None:
        self.governance = governance

    def execute(self, organization_id: int | None = None) -> list[SystemLimitDTO]:
        return self.governance.list_system_limits(organization_id)


class UpsertSystemLimit:
    def __init__(self, governance: GovernanceRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]) -> SystemLimitDTO:
        limit = self.governance.upsert_system_limit(payload)
        _audit(self.audit, actor, "system_limit_upserted", "system_limit", limit.key, after={"value": limit.value, "unit": limit.unit})
        self.transaction.commit()
        return limit


class ListRetentionPolicies:
    def __init__(self, governance: GovernanceRepository) -> None:
        self.governance = governance

    def execute(self, organization_id: int | None = None) -> list[RetentionPolicyDTO]:
        return self.governance.list_retention_policies(organization_id)


class UpsertRetentionPolicy:
    def __init__(self, governance: GovernanceRepository, audit: SqlAlchemyAuditEventRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.audit = audit
        self.transaction = transaction

    def execute(self, actor: Any, payload: dict[str, Any]) -> RetentionPolicyDTO:
        policy = self.governance.upsert_retention_policy(payload)
        _audit(self.audit, actor, "retention_policy_upserted", "retention_policy", policy.resource_type, after={"retention_days": policy.retention_days})
        self.transaction.commit()
        return policy


class BootstrapGovernanceDefaults:
    def __init__(self, governance: GovernanceRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.transaction = transaction

    def execute(self) -> None:
        for payload in DEFAULT_SYSTEM_LIMITS:
            self.governance.upsert_system_limit(payload)
        for payload in DEFAULT_RETENTION_POLICIES:
            self.governance.upsert_retention_policy(payload)
        self.transaction.commit()


def _audit(audit: SqlAlchemyAuditEventRepository, actor: Any, action: str, resource_type: str, resource_id: str, after: dict | None = None) -> None:
    audit.append(
        AuditEvent(
            id=f"aud_{uuid4().hex}",
            organization_id=getattr(actor, "organization_id", None),
            actor_type="user",
            actor_id=_actor_id(actor),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            after=after,
            occurred_at=datetime.now(UTC),
        )
    )


def _actor_id(actor: Any) -> str | None:
    value = getattr(actor, "id", None)
    return str(value) if value is not None else None
