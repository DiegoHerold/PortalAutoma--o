from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    key: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(180))
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id"), nullable=True, index=True)
    automation_version_id: Mapped[int | None] = mapped_column(ForeignKey("automation_versions.id"), nullable=True, index=True)
    flow_id: Mapped[str | None] = mapped_column(ForeignKey("flows.id"), nullable=True, index=True)
    flow_version_id: Mapped[str | None] = mapped_column(ForeignKey("flow_versions.id"), nullable=True, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, default="automation", index=True)

    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="America/Sao_Paulo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    schedule_type: Mapped[str] = mapped_column(String(40), nullable=False, default="cron", index=True)
    recurrence_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    weekdays_json: Mapped[list | None] = mapped_column(JSONB)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False, default="08:00")
    specific_date: Mapped[date | None] = mapped_column(Date)
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    misfire_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="run_once_now")
    max_catch_up_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    misfire_grace_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    overlap_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="forbid")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(120), index=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    automation = relationship("Automation", back_populates="schedules")
    jobs = relationship("Job", back_populates="schedule")


class ScheduleExecutionRecord(Base):
    __tablename__ = "schedule_executions"
    __table_args__ = (UniqueConstraint("schedule_id", "scheduled_for", name="uq_schedule_executions_schedule_time"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, default="scheduled")
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    flow_execution_id: Mapped[str | None] = mapped_column(ForeignKey("flow_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    failure_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
