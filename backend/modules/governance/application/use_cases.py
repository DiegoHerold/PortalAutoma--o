from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.governance.application.dto import AuditEventDTO, RetentionPolicyDTO, SecretDTO, SecretGrantDTO, SecretVersionDTO, SystemLimitDTO
from modules.governance.application.ports import GovernanceRepository, SecretCipher, TransactionManager
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository


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
    """Cria a linha dos limites que ainda não existem (escopo global), com o padrão do catálogo.

    Nunca regrava um valor existente: antes, cada início do Portal voltava os limites e as
    políticas ao padrão e apagava o que alguém tinha mudado. A limpeza do sistema não precisa
    de linha: sem ela, vale o padrão do catálogo (``domain/configuracoes.py``).
    """

    def __init__(self, governance: GovernanceRepository, transaction: TransactionManager) -> None:
        self.governance = governance
        self.transaction = transaction

    def execute(self) -> None:
        from modules.governance.domain.configuracoes import LIMITES
        from modules.governance.infrastructure.repositories.sqlalchemy_configuracoes import UNIDADE_NA_TABELA

        existentes = {item.key for item in self.governance.list_system_limits() if item.organization_id is None}
        for item in LIMITES:
            if item.origem != "portal" or item.chave in existentes:
                continue
            self.governance.upsert_system_limit({"key": item.chave, "value": item.padrao, "description": item.descricao,
                                                 "unit": UNIDADE_NA_TABELA.get(item.unidade, item.unidade)})
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
