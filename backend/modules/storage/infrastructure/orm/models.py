from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StoredObjectRecord(Base):
    __tablename__ = "stored_objects"
    __table_args__ = (UniqueConstraint("bucket", "object_key", name="uq_stored_object_location"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    etag: Mapped[str | None] = mapped_column(String(180))
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadSessionRecord(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stored_object_id: Mapped[str] = mapped_column(ForeignKey("stored_objects.id"), nullable=False, index=True)
    upload_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expected_size_bytes: Mapped[int | None] = mapped_column(Integer)
    expected_sha256: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aborted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_execution_created", "execution_id", "created_at"),
        Index("ix_artifacts_attempt_status", "execution_attempt_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    stored_object_id: Mapped[str | None] = mapped_column(ForeignKey("stored_objects.id"), nullable=True, index=True)
    upload_session_id: Mapped[str | None] = mapped_column(ForeignKey("upload_sessions.id"), nullable=True, index=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    artifact_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class ArtifactUploadSessionRecord(Base):
    __tablename__ = "artifact_upload_sessions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "upload_session_id", name="uq_artifact_upload_session_pair"),
        UniqueConstraint("upload_session_id", name="uq_artifact_upload_session_upload"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_session_id: Mapped[str] = mapped_column(ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
