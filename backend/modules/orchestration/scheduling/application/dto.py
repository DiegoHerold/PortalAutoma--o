from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ScheduleDTO:
    id: int | None
    key: str | None
    name: str | None
    automation_id: int | None
    automation_version_id: int | None
    flow_id: str | None
    flow_version_id: str | None
    target_type: str
    cron_expression: str | None
    timezone: str
    is_active: bool
    status: str
    schedule_type: str
    recurrence_type: str
    time_of_day: str
    weekdays: list[int] | None
    day_of_month: int | None
    specific_date: date | None
    interval_seconds: int | None
    is_one_time: bool
    payload: dict[str, Any]
    misfire_policy: str
    max_catch_up_runs: int
    misfire_grace_seconds: int
    overlap_policy: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_dispatched_at: datetime | None
    created_by: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    paused_at: datetime | None = None
    archived_at: datetime | None = None


@dataclass(frozen=True)
class ScheduleExecutionDTO:
    id: str
    schedule_id: int
    scheduled_for: datetime
    status: str
    trigger_type: str
    execution_id: str | None
    flow_execution_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any] | None
    failure_summary: str | None
    created_at: datetime


@dataclass(frozen=True)
class ScheduleCalendarProgressDTO:
    total: int
    succeeded: int
    running: int
    failed: int
    pending: int


@dataclass(frozen=True)
class ScheduleCalendarItemDTO:
    id: str
    schedule_id: int
    schedule_execution_id: str | None
    execution_id: str | None
    flow_execution_id: str | None
    target_type: str
    target_id: str | None
    target_version: str | None
    target_name: str
    schedule_name: str | None
    planned_start: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    effective_end: datetime | None
    status: str
    temporal_status: str
    reason: str | None
    progress: ScheduleCalendarProgressDTO | None
    responsible: str | None
    agent: str | None
    duration_seconds: float | None
    estimated_duration_seconds: float | None
    estimation_confidence: str | None
    is_estimated: bool
    recurrence_type: str
    schedule_type: str
    timezone: str
    is_one_time: bool
    overlap_group: int | None = None
    overlap_index: int | None = None
    overlap_count: int | None = None


@dataclass(frozen=True)
class ScheduleCalendarSummaryDTO:
    total: int
    completed: int
    running: int
    failed: int
    future: int
    cancelled: int
    skipped: int
    peak_from: datetime | None
    peak_to: datetime | None
    peak_count: int


@dataclass(frozen=True)
class ScheduleCalendarDensityBucketDTO:
    bucket_from: datetime
    bucket_to: datetime
    count: int
    level: str


@dataclass(frozen=True)
class ScheduleCalendarRangeDTO:
    date_from: datetime
    date_to: datetime
    timezone: str


@dataclass(frozen=True)
class ScheduleCalendarResultDTO:
    range: ScheduleCalendarRangeDTO
    items: list[ScheduleCalendarItemDTO]
    summary: ScheduleCalendarSummaryDTO
    density: list[ScheduleCalendarDensityBucketDTO]


def to_payload(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
