from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.orchestration.scheduling.application.dto import ScheduleDTO, ScheduleExecutionDTO
from modules.orchestration.scheduling.infrastructure.orm.models import Schedule, ScheduleExecutionRecord


ACTIVE_SCHEDULE_EXECUTION_STATUSES = {"created", "running"}


class SqlAlchemyScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, schedule: ScheduleDTO) -> ScheduleDTO:
        row = Schedule(**_schedule_dict(schedule, include_id=False))
        self.db.add(row)
        self.db.flush()
        if row.key is None:
            row.key = f"sch_{row.id}"
            self.db.add(row)
            self.db.flush()
        return _schedule_to_dto(row)

    def save(self, schedule: ScheduleDTO) -> ScheduleDTO:
        if schedule.id is None:
            return self.add(schedule)
        row = self.db.get(Schedule, schedule.id)
        if row is None:
            return self.add(schedule)
        for key, value in _schedule_dict(schedule, include_id=False).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _schedule_to_dto(row)

    def get(self, schedule_id: int) -> ScheduleDTO | None:
        row = self.db.get(Schedule, schedule_id)
        return _schedule_to_dto(row) if row else None

    def get_by_key(self, key: str) -> ScheduleDTO | None:
        row = self.db.scalar(select(Schedule).where(Schedule.key == key))
        return _schedule_to_dto(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> list[ScheduleDTO]:
        rows = self.db.scalars(select(Schedule).order_by(Schedule.created_at.desc()).offset(offset).limit(limit)).all()
        return [_schedule_to_dto(row) for row in rows]

    def due(self, now: datetime, limit: int = 100) -> list[ScheduleDTO]:
        rows = self.db.scalars(
            select(Schedule)
            .where(
                Schedule.is_active.is_(True),
                Schedule.status == "active",
                Schedule.next_run_at.is_not(None),
                Schedule.next_run_at <= now,
                Schedule.archived_at.is_(None),
            )
            .order_by(Schedule.next_run_at.asc(), Schedule.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_schedule_to_dto(row) for row in rows]


class SqlAlchemyScheduleExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, execution: ScheduleExecutionDTO) -> ScheduleExecutionDTO:
        row = ScheduleExecutionRecord(**execution.__dict__)
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def save(self, execution: ScheduleExecutionDTO) -> ScheduleExecutionDTO:
        row = self.db.get(ScheduleExecutionRecord, execution.id)
        if row is None:
            return self.add(execution)
        for key, value in execution.__dict__.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def get(self, schedule_execution_id: str) -> ScheduleExecutionDTO | None:
        row = self.db.get(ScheduleExecutionRecord, schedule_execution_id)
        return _execution_to_dto(row) if row else None

    def get_by_schedule_time(self, schedule_id: int, scheduled_for: datetime) -> ScheduleExecutionDTO | None:
        row = self.db.scalar(select(ScheduleExecutionRecord).where(ScheduleExecutionRecord.schedule_id == schedule_id, ScheduleExecutionRecord.scheduled_for == scheduled_for))
        return _execution_to_dto(row) if row else None

    def list_for_schedule(self, schedule_id: int) -> list[ScheduleExecutionDTO]:
        rows = self.db.scalars(select(ScheduleExecutionRecord).where(ScheduleExecutionRecord.schedule_id == schedule_id).order_by(ScheduleExecutionRecord.scheduled_for.desc())).all()
        return [_execution_to_dto(row) for row in rows]

    def active_for_schedule(self, schedule_id: int) -> list[ScheduleExecutionDTO]:
        rows = self.db.scalars(select(ScheduleExecutionRecord).where(ScheduleExecutionRecord.schedule_id == schedule_id, ScheduleExecutionRecord.status.in_(ACTIVE_SCHEDULE_EXECUTION_STATUSES))).all()
        return [_execution_to_dto(row) for row in rows]

    def list_active(self, limit: int = 100) -> list[ScheduleExecutionDTO]:
        rows = self.db.scalars(
            select(ScheduleExecutionRecord)
            .where(ScheduleExecutionRecord.status.in_(ACTIVE_SCHEDULE_EXECUTION_STATUSES))
            .order_by(ScheduleExecutionRecord.created_at.asc())
            .limit(limit)
        ).all()
        return [_execution_to_dto(row) for row in rows]


def _schedule_dict(schedule: ScheduleDTO, *, include_id: bool) -> dict[str, Any]:
    data = {
        "key": schedule.key,
        "name": schedule.name,
        "automation_id": schedule.automation_id,
        "automation_version_id": schedule.automation_version_id,
        "flow_id": schedule.flow_id,
        "flow_version_id": schedule.flow_version_id,
        "target_type": schedule.target_type,
        "cron_expression": schedule.cron_expression,
        "timezone": schedule.timezone,
        "is_active": schedule.is_active,
        "status": schedule.status,
        "schedule_type": schedule.schedule_type,
        "recurrence_type": schedule.recurrence_type,
        "weekdays_json": schedule.weekdays,
        "day_of_month": schedule.day_of_month,
        "time_of_day": schedule.time_of_day,
        "specific_date": schedule.specific_date,
        "interval_seconds": schedule.interval_seconds,
        "is_one_time": schedule.is_one_time,
        "payload": schedule.payload or {},
        "misfire_policy": schedule.misfire_policy,
        "max_catch_up_runs": schedule.max_catch_up_runs,
        "misfire_grace_seconds": schedule.misfire_grace_seconds,
        "overlap_policy": schedule.overlap_policy,
        "next_run_at": schedule.next_run_at,
        "last_run_at": schedule.last_run_at,
        "last_dispatched_at": schedule.last_dispatched_at,
        "created_by": schedule.created_by,
        "paused_at": schedule.paused_at,
        "archived_at": schedule.archived_at,
    }
    if include_id:
        data["id"] = schedule.id
    return data


def _schedule_to_dto(row: Schedule) -> ScheduleDTO:
    return ScheduleDTO(
        id=row.id,
        key=row.key,
        name=row.name,
        automation_id=row.automation_id,
        automation_version_id=row.automation_version_id,
        flow_id=row.flow_id,
        flow_version_id=row.flow_version_id,
        target_type=row.target_type,
        cron_expression=row.cron_expression,
        timezone=row.timezone,
        is_active=row.is_active,
        status=row.status,
        schedule_type=row.schedule_type,
        recurrence_type=row.recurrence_type,
        time_of_day=row.time_of_day,
        weekdays=row.weekdays_json,
        day_of_month=row.day_of_month,
        specific_date=row.specific_date,
        interval_seconds=row.interval_seconds,
        is_one_time=row.is_one_time,
        payload=row.payload or {},
        misfire_policy=row.misfire_policy,
        max_catch_up_runs=row.max_catch_up_runs,
        misfire_grace_seconds=row.misfire_grace_seconds,
        overlap_policy=row.overlap_policy,
        next_run_at=row.next_run_at,
        last_run_at=row.last_run_at,
        last_dispatched_at=row.last_dispatched_at,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        paused_at=row.paused_at,
        archived_at=row.archived_at,
    )


def _execution_to_dto(row: ScheduleExecutionRecord) -> ScheduleExecutionDTO:
    return ScheduleExecutionDTO(
        id=row.id,
        schedule_id=row.schedule_id,
        scheduled_for=row.scheduled_for,
        status=row.status,
        trigger_type=row.trigger_type,
        execution_id=row.execution_id,
        flow_execution_id=row.flow_execution_id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        result=row.result,
        failure_summary=row.failure_summary,
        created_at=row.created_at,
    )
