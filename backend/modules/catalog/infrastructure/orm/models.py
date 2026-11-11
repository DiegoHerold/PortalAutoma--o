from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class CatalogCategoryRecord(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CatalogAutomationRecord(Base):
    __tablename__ = "automations"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    key: Mapped[str | None] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    executor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    package_url: Mapped[str | None] = mapped_column(Text)
    package_sha256: Mapped[str | None] = mapped_column(String(120))
    default_priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    tags_json: Mapped[list | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CatalogAutomationSourceRecord(Base):
    __tablename__ = "automation_sources"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    integration_id: Mapped[int | None] = mapped_column(ForeignKey("github_integrations.id"))
    owner: Mapped[str | None] = mapped_column(String(200))
    repository: Mapped[str | None] = mapped_column(String(200))
    branch: Mapped[str | None] = mapped_column(String(200))
    automation_path: Mapped[str | None] = mapped_column(Text)
    manifest_path: Mapped[str | None] = mapped_column(Text)
    workspace_path: Mapped[str | None] = mapped_column(Text)
    last_commit_sha: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str | None] = mapped_column(String(30))
    original_filename: Mapped[str | None] = mapped_column(Text)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_sha256: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GithubIntegrationRecord(Base):
    __tablename__ = "github_integrations"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    account_login: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    connected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CatalogAutomationVersionRecord(Base):
    __tablename__ = "automation_versions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("automation_sources.id"))
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest_id: Mapped[str | None] = mapped_column(ForeignKey("automation_manifests.id"))
    package_id: Mapped[str | None] = mapped_column(ForeignKey("automation_packages.id"))
    runtime_version_id: Mapped[str | None] = mapped_column(ForeignKey("runtime_versions.id"))
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    runtime_id: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime_version: Mapped[str | None] = mapped_column(String(40))
    entrypoint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entrypoint: Mapped[dict] = mapped_column(JSONB, nullable=False)
    application_type: Mapped[str] = mapped_column(String(20), nullable=False, default="source")
    application_path: Mapped[str | None] = mapped_column(Text)
    artifact_bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    artifact_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(120), nullable=False)
    source_commit_sha: Mapped[str | None] = mapped_column(String(64))
    source_path: Mapped[str | None] = mapped_column(Text)
    release_notes: Mapped[str | None] = mapped_column(Text)
    source_repository: Mapped[str | None] = mapped_column(Text)
    source_branch: Mapped[str | None] = mapped_column(String(200))
    source_tag: Mapped[str | None] = mapped_column(String(200))
    build_id: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[str | None] = mapped_column(String(255))
    published_by: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="validating")
    validation_errors: Mapped[list | None] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AutomationManifestRecord(Base):
    __tablename__ = "automation_manifests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_version_id: Mapped[int] = mapped_column(ForeignKey("automation_versions.id"), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    validation_errors: Mapped[list | None] = mapped_column(JSONB)
    validator_version: Mapped[str] = mapped_column(String(40), nullable=False, default="catalog-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationPackageRecord(Base):
    __tablename__ = "automation_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_version_id: Mapped[int] = mapped_column(ForeignKey("automation_versions.id"), nullable=False, index=True)
    stored_object_id: Mapped[str] = mapped_column(ForeignKey("stored_objects.id"), nullable=False, index=True)
    package_format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str | None] = mapped_column(Text)
    signature_algorithm: Mapped[str | None] = mapped_column(String(80))
    signing_key_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    validation_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuntimeRecord(Base):
    __tablename__ = "runtimes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RuntimeVersionRecord(Base):
    __tablename__ = "runtime_versions"
    __table_args__ = (
        UniqueConstraint(
            "runtime_id",
            "version",
            "operating_system",
            "architecture",
            name="uq_runtime_version_platform",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    runtime_id: Mapped[str] = mapped_column(ForeignKey("runtimes.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    operating_system: Mapped[str] = mapped_column(String(80), nullable=False)
    architecture: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    minimum_agent_version: Mapped[str | None] = mapped_column(String(50))
    supported_entrypoints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    supported_execution_modes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuntimeArtifactRecord(Base):
    __tablename__ = "runtime_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    runtime_version_id: Mapped[str] = mapped_column(ForeignKey("runtime_versions.id"), nullable=False, index=True)
    stored_object_id: Mapped[str] = mapped_column(ForeignKey("stored_objects.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str | None] = mapped_column(Text)
    signature_algorithm: Mapped[str | None] = mapped_column(String(80))
    signing_key_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationItemRecord(Base):
    """Item do cadastro de uma automação (Fase 5): empresa, nota, cliente..."""

    __tablename__ = "automation_items"
    __table_args__ = (UniqueConstraint("automation_id", "chave", name="uq_automation_items_chave"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    chave: Mapped[str] = mapped_column(String(120), nullable=False)
    rotulo: Mapped[str] = mapped_column(String(255), nullable=False)
    grupo_chave: Mapped[str | None] = mapped_column(String(120), nullable=True)
    atributos: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(120))
    updated_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AutomationFormRecord(Base):
    """Campos da automação editados no Portal (Fase 7). Sem linha: vale o que o manifesto sugere."""

    __tablename__ = "automation_forms"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True)
    entrada: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    colunas: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
