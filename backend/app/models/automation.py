from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class Automation(BaseModel):
    __tablename__ = "automations"

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    # Stable technical identity sourced from the automation.yaml manifest's `id` field
    # (e.g. "dominio.atualizar"). Distinct from `slug`/`name`, which may change.
    # NOTE: the numeric `id` column (BaseModel) remains the immutable internal
    # identifier used by every existing FK (jobs, triggers, schedules, worker
    # preferences) — we deliberately did not introduce a parallel public string id
    # to avoid touching that surface. See docs/automation-catalog.md.
    key: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text())
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    executor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    package_url: Mapped[str | None] = mapped_column(Text())
    package_sha256: Mapped[str | None] = mapped_column(String(120))
    default_priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    tags_json: Mapped[list | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    category = relationship("Category", back_populates="automations")
    jobs = relationship("Job", back_populates="automation")
    triggers = relationship("Trigger", back_populates="automation", foreign_keys="Trigger.automation_id")
    schedules = relationship("Schedule", back_populates="automation")
    worker_preferences = relationship("AutomationWorkerPreference", back_populates="automation")
    sources = relationship(
        "AutomationSource", back_populates="automation", cascade="all, delete-orphan"
    )
    versions = relationship(
        "AutomationVersion",
        back_populates="automation",
        cascade="all, delete-orphan",
        order_by="AutomationVersion.created_at.desc()",
    )
