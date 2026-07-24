from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Schedule(BaseModel):
    __tablename__ = "schedules"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False)

    # cron_expression stays the single source of truth for actual dispatch
    # (sync_schedules) and calendar math (croniter) -- it's always computed
    # server-side from the structured fields below, never hand-edited by the
    # user anymore. The structured fields exist so the UI can show/edit
    # "mensal, dia 15, 08:00" instead of parsing "0 8 15 * *" back and forth.
    cron_expression: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="America/Sao_Paulo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # daily | weekly | monthly | once
    recurrence_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    weekdays_json: Mapped[list | None] = mapped_column(JSONB)  # [0..6], Mon=0 .. Sun=6 -- "weekly"
    day_of_month: Mapped[int | None] = mapped_column(Integer)  # 1-31, or 0 for "last day" -- "monthly"
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False, default="08:00")  # "HH:MM"
    specific_date: Mapped[date | None] = mapped_column(Date)  # "once"
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    automation = relationship("Automation", back_populates="schedules")
    jobs = relationship("Job", back_populates="schedule")
