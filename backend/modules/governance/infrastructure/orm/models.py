from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("access_organizations.id"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    ip: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SecretRecord(Base):
    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_secrets_org_key"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("access_organizations.id"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SecretVersionRecord(Base):
    __tablename__ = "secret_versions"
    __table_args__ = (UniqueConstraint("secret_id", "version", name="uq_secret_versions_secret_version"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    secret_id: Mapped[str] = mapped_column(ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecretGrantRecord(Base):
    __tablename__ = "secret_grants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    secret_id: Mapped[str] = mapped_column(ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True)
    grantee_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    grantee_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SystemLimitRecord(Base):
    __tablename__ = "system_limits"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_system_limits_scope_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("access_organizations.id"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RetentionPolicyRecord(Base):
    __tablename__ = "retention_policies"
    __table_args__ = (UniqueConstraint("organization_id", "resource_type", name="uq_retention_policy_scope_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("access_organizations.id"), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_after_days: Mapped[int | None] = mapped_column(Integer)
    delete_after_days: Mapped[int | None] = mapped_column(Integer)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AutomationRetentionRecord(Base):
    """Dias de imagens e de logs por automação (Fase 6). Sem linha ou com ``None``: nada sai."""

    __tablename__ = "automation_retention"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True)
    imagens_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logs_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
