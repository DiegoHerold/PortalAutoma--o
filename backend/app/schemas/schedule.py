from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, model_validator


class ScheduleCreate(BaseModel):
    automation_id: int | None = None
    automation_version_id: int | None = None
    flow_id: str | None = None
    flow_version_id: str | None = None
    target_type: str = "automation"
    key: str | None = None
    name: str | None = None
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True

    schedule_type: str | None = None  # cron | once | interval
    cron_expression: str | None = None
    recurrence_type: str = "daily"  # daily | weekly | monthly | once
    time_of_day: str = "08:00"
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    interval_seconds: int | None = None

    payload: dict[str, Any] | None = None
    misfire_policy: str | None = None
    max_catch_up_runs: int | None = None
    misfire_grace_seconds: int | None = None
    overlap_policy: str | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def _check_recurrence_fields(self) -> "ScheduleCreate":
        if self.target_type == "automation" and self.automation_id is None and self.automation_version_id is None:
            raise ValueError("automation_id or automation_version_id is required for automation schedules.")
        if self.target_type == "flow" and self.flow_version_id is None:
            raise ValueError("flow_version_id is required for Flow schedules.")
        if self.schedule_type == "interval":
            if self.interval_seconds is None or self.interval_seconds < 60:
                raise ValueError("interval_seconds must be greater than or equal to 60.")
            return self
        if self.recurrence_type == "weekly" and not self.weekdays:
            raise ValueError("weekdays is required for recurrence_type='weekly'.")
        if self.recurrence_type == "monthly" and self.day_of_month is None:
            raise ValueError("day_of_month is required for recurrence_type='monthly'.")
        if self.recurrence_type == "once" and self.specific_date is None:
            raise ValueError("specific_date is required for recurrence_type='once'.")
        return self


class ScheduleUpdate(BaseModel):
    automation_id: int | None = None
    automation_version_id: int | None = None
    flow_id: str | None = None
    flow_version_id: str | None = None
    target_type: str | None = None
    key: str | None = None
    name: str | None = None
    timezone: str | None = None
    is_active: bool | None = None

    schedule_type: str | None = None
    cron_expression: str | None = None
    recurrence_type: str | None = None
    time_of_day: str | None = None
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    interval_seconds: int | None = None

    payload: dict[str, Any] | None = None
    misfire_policy: str | None = None
    max_catch_up_runs: int | None = None
    misfire_grace_seconds: int | None = None
    overlap_policy: str | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def _check_update_fields(self) -> "ScheduleUpdate":
        if self.schedule_type == "interval" and self.interval_seconds is not None and self.interval_seconds < 60:
            raise ValueError("interval_seconds must be greater than or equal to 60.")
        return self


class ScheduleRead(BaseModel):
    id: int
    automation_id: int | None = None
    automation_version_id: int | None = None
    flow_id: str | None = None
    flow_version_id: str | None = None
    target_type: str = "automation"
    key: str | None = None
    name: str | None = None
    cron_expression: str | None
    timezone: str
    is_active: bool
    recurrence_type: str
    time_of_day: str
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    is_one_time: bool
    last_dispatched_at: datetime | None = None
    status: str | None = None
    schedule_type: str | None = None
    interval_seconds: int | None = None
    payload: dict[str, Any] | None = None
    misfire_policy: str | None = None
    max_catch_up_runs: int | None = None
    misfire_grace_seconds: int | None = None
    overlap_policy: str | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None

    class Config:
        from_attributes = True
        populate_by_name = True

    @classmethod
    def model_validate(cls, obj, **kwargs):  # type: ignore[override]
        if hasattr(obj, "weekdays_json") and not isinstance(obj, dict):
            data = {
                "id": obj.id,
                "automation_id": obj.automation_id,
                "automation_version_id": getattr(obj, "automation_version_id", None),
                "flow_id": getattr(obj, "flow_id", None),
                "flow_version_id": getattr(obj, "flow_version_id", None),
                "target_type": getattr(obj, "target_type", "automation"),
                "key": getattr(obj, "key", None),
                "name": getattr(obj, "name", None),
                "cron_expression": obj.cron_expression,
                "timezone": obj.timezone,
                "is_active": obj.is_active,
                "recurrence_type": obj.recurrence_type,
                "time_of_day": obj.time_of_day,
                "weekdays": obj.weekdays_json,
                "day_of_month": obj.day_of_month,
                "specific_date": obj.specific_date,
                "is_one_time": obj.is_one_time,
                "last_dispatched_at": obj.last_dispatched_at,
                "status": getattr(obj, "status", None),
                "schedule_type": getattr(obj, "schedule_type", None),
                "interval_seconds": getattr(obj, "interval_seconds", None),
                "payload": getattr(obj, "payload", None),
                "misfire_policy": getattr(obj, "misfire_policy", None),
                "max_catch_up_runs": getattr(obj, "max_catch_up_runs", None),
                "misfire_grace_seconds": getattr(obj, "misfire_grace_seconds", None),
                "overlap_policy": getattr(obj, "overlap_policy", None),
                "next_run_at": getattr(obj, "next_run_at", None),
                "last_run_at": getattr(obj, "last_run_at", None),
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class ScheduleOccurrence(BaseModel):
    schedule_id: int
    automation_id: int
    automation_name: str
    category_id: int | None = None
    recurrence_type: str
    occurs_at: datetime
    status: str
    job_id: int | None = None
    execution_id: str | None = None
    schedule_execution_id: str | None = None
