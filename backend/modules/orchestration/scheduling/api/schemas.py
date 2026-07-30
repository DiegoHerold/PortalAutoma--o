from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ScheduleCreateRequest(BaseModel):
    automation_id: int | None = None
    automation_version_id: int | None = None
    flow_id: str | None = None
    flow_version_id: str | None = None
    target_type: str = "automation"
    key: str | None = None
    name: str | None = None
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True
    schedule_type: str | None = None
    cron_expression: str | None = None
    recurrence_type: str = "daily"
    time_of_day: str = "08:00"
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    interval_seconds: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    misfire_policy: str | None = None
    max_catch_up_runs: int | None = None
    misfire_grace_seconds: int | None = None
    overlap_policy: str | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def _check_recurrence_fields(self) -> "ScheduleCreateRequest":
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


class ScheduleUpdateRequest(BaseModel):
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
    def _check_update_fields(self) -> "ScheduleUpdateRequest":
        if self.schedule_type == "interval" and self.interval_seconds is not None and self.interval_seconds < 60:
            raise ValueError("interval_seconds must be greater than or equal to 60.")
        return self


class ScheduleResponse(BaseModel):
    id: int
    automation_id: int | None = None
    automation_version_id: int | None = None
    flow_id: str | None = None
    flow_version_id: str | None = None
    target_type: str = "automation"
    key: str | None = None
    name: str | None = None
    cron_expression: str | None = None
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


class ScheduleExecutionResponse(BaseModel):
    id: str
    schedule_id: int
    scheduled_for: datetime
    status: str
    trigger_type: str
    execution_id: str | None = None
    flow_execution_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    failure_summary: str | None = None
    created_at: datetime


class ScheduleCalendarProgressResponse(BaseModel):
    total: int
    succeeded: int
    running: int
    failed: int
    pending: int


class ScheduleCalendarItemResponse(BaseModel):
    id: str
    schedule_id: int
    schedule_execution_id: str | None = None
    execution_id: str | None = None
    flow_execution_id: str | None = None
    target_type: str
    target_id: str | None = None
    target_version: str | None = None
    target_name: str
    schedule_name: str | None = None
    planned_start: datetime
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    effective_end: datetime | None = None
    status: str
    temporal_status: str
    reason: str | None = None
    progress: ScheduleCalendarProgressResponse | None = None
    responsible: str | None = None
    agent: str | None = None
    duration_seconds: float | None = None
    estimated_duration_seconds: float | None = None
    estimation_confidence: str | None = None
    is_estimated: bool = False
    recurrence_type: str
    schedule_type: str
    timezone: str
    is_one_time: bool
    overlap_group: int | None = None
    overlap_index: int | None = None
    overlap_count: int | None = None


class ScheduleCalendarSummaryResponse(BaseModel):
    total: int
    completed: int
    running: int
    failed: int
    future: int
    cancelled: int
    skipped: int
    peak_from: datetime | None = None
    peak_to: datetime | None = None
    peak_count: int = 0


class ScheduleCalendarDensityBucketResponse(BaseModel):
    bucket_from: datetime
    bucket_to: datetime
    count: int
    level: str


class ScheduleCalendarRangeResponse(BaseModel):
    date_from: datetime
    date_to: datetime
    timezone: str


class ScheduleCalendarResponse(BaseModel):
    range: ScheduleCalendarRangeResponse
    items: list[ScheduleCalendarItemResponse]
    summary: ScheduleCalendarSummaryResponse
    density: list[ScheduleCalendarDensityBucketResponse]


class SchedulePreviewRequest(BaseModel):
    """Espelha os campos de recorrencia de ScheduleCreateRequest para pre-visualizar
    as proximas ocorrencias antes de salvar (nao persiste nada)."""

    timezone: str = "America/Sao_Paulo"
    schedule_type: str | None = None
    cron_expression: str | None = None
    recurrence_type: str = "daily"
    time_of_day: str = "08:00"
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None
    interval_seconds: int | None = None
    count: int = 5


class SchedulePreviewResponse(BaseModel):
    occurrences: list[datetime]
