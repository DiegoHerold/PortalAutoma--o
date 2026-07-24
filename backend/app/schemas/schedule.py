from datetime import date, datetime

from pydantic import BaseModel, model_validator


class ScheduleCreate(BaseModel):
    automation_id: int
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True

    recurrence_type: str  # daily | weekly | monthly | once
    time_of_day: str  # "HH:MM"
    weekdays: list[int] | None = None  # 0=Mon .. 6=Sun, required for "weekly"
    day_of_month: int | None = None  # 1-31 or 0="last day", required for "monthly"
    specific_date: date | None = None  # required for "once"

    @model_validator(mode="after")
    def _check_recurrence_fields(self) -> "ScheduleCreate":
        if self.recurrence_type == "weekly" and not self.weekdays:
            raise ValueError("weekdays é obrigatório para recurrence_type='weekly'.")
        if self.recurrence_type == "monthly" and self.day_of_month is None:
            raise ValueError("day_of_month é obrigatório para recurrence_type='monthly'.")
        if self.recurrence_type == "once" and self.specific_date is None:
            raise ValueError("specific_date é obrigatório para recurrence_type='once'.")
        return self


class ScheduleUpdate(ScheduleCreate):
    pass


class ScheduleRead(BaseModel):
    id: int
    automation_id: int
    cron_expression: str
    timezone: str
    is_active: bool
    recurrence_type: str
    time_of_day: str
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    is_one_time: bool
    last_dispatched_at: datetime | None = None

    class Config:
        from_attributes = True
        populate_by_name = True

    @classmethod
    def model_validate(cls, obj, **kwargs):  # type: ignore[override]  # noqa: keep close to ScheduleRead for readability
        # Schedule.weekdays_json (DB column) -> weekdays (API field name).
        if hasattr(obj, "weekdays_json") and not isinstance(obj, dict):
            data = {
                "id": obj.id,
                "automation_id": obj.automation_id,
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
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class ScheduleOccurrence(BaseModel):
    """One occurrence of a Schedule inside a calendar date range, merged with
    the Job it actually produced (when the occurrence is in the past)."""

    schedule_id: int
    automation_id: int
    automation_name: str
    category_id: int | None = None
    recurrence_type: str
    occurs_at: datetime
    status: str  # upcoming | missed | queued | running | success | failed | cancelled
    job_id: int | None = None
