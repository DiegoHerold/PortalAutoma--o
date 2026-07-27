from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
