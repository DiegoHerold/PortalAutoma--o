from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Job(BaseModel):
    __tablename__ = "jobs"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), nullable=True)
    trigger_id: Mapped[int | None] = mapped_column(ForeignKey("triggers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text())

    automation = relationship("Automation", back_populates="jobs")
    requested_by_user = relationship("User", back_populates="requested_jobs")
    assigned_worker = relationship("Worker", back_populates="jobs")
    executions = relationship("Execution", back_populates="job")
    schedule = relationship("Schedule", back_populates="jobs")
