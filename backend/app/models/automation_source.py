from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AutomationSource(BaseModel):
    """
    Where an automation's code comes from. One automation may accumulate multiple
    sources over time in principle, but in this implementation each Automation has
    a single active source (github or manual_upload) that new versions are created
    against — see AutomationSourceRepository.get_for_automation().
    """

    __tablename__ = "automation_sources"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # AutomationSourceType

    # --- GitHub fields ---
    integration_id: Mapped[int | None] = mapped_column(ForeignKey("github_integrations.id"))
    owner: Mapped[str | None] = mapped_column(String(200))
    repository: Mapped[str | None] = mapped_column(String(200))
    branch: Mapped[str | None] = mapped_column(String(200))
    automation_path: Mapped[str | None] = mapped_column(Text())
    manifest_path: Mapped[str | None] = mapped_column(Text())
    workspace_path: Mapped[str | None] = mapped_column(Text())
    last_commit_sha: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str | None] = mapped_column(String(30))  # AutomationSyncStatus

    # --- Manual upload fields ---
    original_filename: Mapped[str | None] = mapped_column(Text())
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_sha256: Mapped[str | None] = mapped_column(String(120))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    automation = relationship("Automation", back_populates="sources")
    integration = relationship("GithubIntegration", back_populates="sources")
    versions = relationship("AutomationVersion", back_populates="source")
