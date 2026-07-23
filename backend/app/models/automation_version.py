from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AutomationVersion(BaseModel):
    """
    An immutable, packaged snapshot of an automation at a specific version.
    The ZIP artifact referenced by artifact_bucket/artifact_object_key is never
    mutated once status leaves `validating` — a new code change always produces a
    new AutomationVersion row (or is rejected if the manifest `version` did not change).
    """

    __tablename__ = "automation_versions"
    __table_args__ = ()

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("automation_sources.id"))

    version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    runtime_id: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime_version: Mapped[str | None] = mapped_column(String(40))

    entrypoint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entrypoint: Mapped[dict] = mapped_column(JSONB, nullable=False)

    application_type: Mapped[str] = mapped_column(String(20), nullable=False, default="source")
    application_path: Mapped[str | None] = mapped_column(Text())

    artifact_bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    artifact_object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(120), nullable=False)

    source_commit_sha: Mapped[str | None] = mapped_column(String(64))
    source_path: Mapped[str | None] = mapped_column(Text())

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="validating")
    validation_errors: Mapped[list | None] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    automation = relationship("Automation", back_populates="versions")
    source = relationship("AutomationSource", back_populates="versions")
