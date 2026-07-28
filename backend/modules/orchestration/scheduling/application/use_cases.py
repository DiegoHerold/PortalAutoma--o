from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from croniter import croniter

from modules.governance.domain.audit import AuditEvent
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.application.ports import ExecutionRepository
from modules.orchestration.flows.application.ports import FlowExecutionRepository
from modules.orchestration.scheduling.application.dto import ScheduleDTO, ScheduleExecutionDTO
from modules.orchestration.scheduling.application.ports import ScheduleExecutionCreator, ScheduleExecutionRepository, ScheduleRepository, OutboxPort, TransactionManager
from modules.orchestration.scheduling.domain import DEFAULT_TIMEZONE, RecurrenceInput, aware, build_cron_expression, calculate_next_run, timezone_or_default


class CreateSchedule:
    def __init__(self, schedules: ScheduleRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, payload: dict[str, Any], *, actor: ActorDTO) -> ScheduleDTO:
        schedule = _schedule_from_payload(payload, actor=actor, existing=None)
        saved = self.schedules.add(schedule)
        if saved.key is None:
            saved = self.schedules.save(replace(saved, key=f"sch_{saved.id}"))
        self.outbox.append_event("schedule.created", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.created", "schedule", str(saved.id), after={"target_type": saved.target_type})
        self.transaction.commit()
        return saved


class UpdateSchedule:
    def __init__(self, schedules: ScheduleRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, schedule_id: int, payload: dict[str, Any], *, actor: ActorDTO) -> ScheduleDTO:
        current = _require_schedule(self.schedules, schedule_id)
        schedule = _schedule_from_payload(payload, actor=actor, existing=current)
        saved = self.schedules.save(schedule)
        self.outbox.append_event("schedule.updated", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.updated", "schedule", str(saved.id))
        self.transaction.commit()
        return saved


class EnableSchedule:
    def __init__(self, schedules: ScheduleRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, schedule_id: int, *, actor: ActorDTO) -> ScheduleDTO:
        schedule = _require_schedule(self.schedules, schedule_id)
        now = utcnow()
        next_run = schedule.next_run_at or _next_run(schedule, now)
        saved = self.schedules.save(replace(schedule, is_active=True, status="active", paused_at=None, next_run_at=next_run))
        self.outbox.append_event("schedule.enabled", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.enabled", "schedule", str(saved.id))
        self.transaction.commit()
        return saved


class PauseSchedule:
    def __init__(self, schedules: ScheduleRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, schedule_id: int, *, actor: ActorDTO) -> ScheduleDTO:
        schedule = _require_schedule(self.schedules, schedule_id)
        saved = self.schedules.save(replace(schedule, is_active=False, status="paused", paused_at=utcnow()))
        self.outbox.append_event("schedule.paused", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.paused", "schedule", str(saved.id))
        self.transaction.commit()
        return saved


class DisableSchedule(PauseSchedule):
    def execute(self, schedule_id: int, *, actor: ActorDTO) -> ScheduleDTO:
        schedule = _require_schedule(self.schedules, schedule_id)
        saved = self.schedules.save(replace(schedule, is_active=False, status="disabled", paused_at=utcnow()))
        self.outbox.append_event("schedule.disabled", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.disabled", "schedule", str(saved.id))
        self.transaction.commit()
        return saved


class ArchiveSchedule(PauseSchedule):
    def execute(self, schedule_id: int, *, actor: ActorDTO) -> ScheduleDTO:
        schedule = _require_schedule(self.schedules, schedule_id)
        saved = self.schedules.save(replace(schedule, is_active=False, status="archived", archived_at=utcnow()))
        self.outbox.append_event("schedule.archived", "schedule", str(saved.id), {"schedule_id": saved.id})
        _audit(self.audit, actor, "schedule.archived", "schedule", str(saved.id))
        self.transaction.commit()
        return saved


class GetSchedule:
    def __init__(self, schedules: ScheduleRepository) -> None:
        self.schedules = schedules

    def execute(self, schedule_id: int) -> ScheduleDTO:
        return _require_schedule(self.schedules, schedule_id)


class ListSchedules:
    def __init__(self, schedules: ScheduleRepository) -> None:
        self.schedules = schedules

    def execute(self, limit: int = 100, offset: int = 0) -> list[ScheduleDTO]:
        return self.schedules.list(limit=limit, offset=offset)


class GetScheduleHistory:
    def __init__(self, executions: ScheduleExecutionRepository) -> None:
        self.executions = executions

    def execute(self, schedule_id: int) -> list[ScheduleExecutionDTO]:
        return self.executions.list_for_schedule(schedule_id)


class GetScheduleExecution:
    def __init__(self, executions: ScheduleExecutionRepository) -> None:
        self.executions = executions

    def execute(self, schedule_execution_id: str) -> ScheduleExecutionDTO:
        execution = self.executions.get(schedule_execution_id)
        if execution is None:
            raise ValueError("ScheduleExecution not found.")
        return execution


class CreateScheduleExecution:
    def __init__(self, executions: ScheduleExecutionRepository, transaction: TransactionManager) -> None:
        self.executions = executions
        self.transaction = transaction

    def execute(self, *, schedule_id: int, scheduled_for: datetime, trigger_type: str = "scheduled") -> ScheduleExecutionDTO:
        existing = self.executions.get_by_schedule_time(schedule_id, scheduled_for)
        if existing is not None:
            return existing
        created = self.executions.add(ScheduleExecutionDTO(id=new_id("sex"), schedule_id=schedule_id, scheduled_for=scheduled_for, status="created", trigger_type=trigger_type, execution_id=None, flow_execution_id=None, started_at=None, completed_at=None, result=None, failure_summary=None, created_at=utcnow()))
        self.transaction.commit()
        return created


class TriggerDueSchedules:
    def __init__(self, schedules: ScheduleRepository, executions: ScheduleExecutionRepository, creator: ScheduleExecutionCreator, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.executions = executions
        self.creator = creator
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, limit: int = 100, now: datetime | None = None) -> dict[str, Any]:
        current = now or utcnow()
        triggered: list[str] = []
        skipped: list[str] = []
        failed_ids: list[str] = []
        errors: list[str] = []
        for schedule in self.schedules.due(current, limit=limit):
            scheduled_for = schedule.next_run_at or current
            try:
                result = _trigger_one(schedule, scheduled_for, current, self.executions, self.creator, self.outbox)
                self.schedules.save(_advance_schedule(schedule, scheduled_for, current))
                if result.status == "skipped":
                    skipped.append(result.id)
                else:
                    triggered.append(result.id)
                self.transaction.commit()
            except Exception as exc:  # noqa: BLE001
                self.transaction.rollback()
                try:
                    failed_execution = _record_trigger_failure(schedule, scheduled_for, current, self.executions, self.outbox, str(exc))
                    self.schedules.save(_advance_schedule(schedule, scheduled_for, current))
                    self.transaction.commit()
                    errors.append(f"schedule {schedule.id}: {exc}")
                    failed_ids.append(failed_execution.id)
                except Exception as failure_exc:  # noqa: BLE001
                    self.transaction.rollback()
                    errors.append(f"schedule {schedule.id}: {exc}; failure_record_error={failure_exc}")
        return {"triggered": triggered, "skipped": skipped, "failed": failed_ids, "errors": errors}


class ReconcileScheduleExecutions:
    def __init__(
        self,
        schedule_executions: ScheduleExecutionRepository,
        executions: ExecutionRepository,
        flow_executions: FlowExecutionRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.schedule_executions = schedule_executions
        self.executions = executions
        self.flow_executions = flow_executions
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, limit: int = 100) -> dict[str, int]:
        reconciled = 0
        for item in self.schedule_executions.list_active(limit=limit):
            status, completed_at, result, summary = self._current_state(item)
            if status not in {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out"}:
                continue
            saved = self.schedule_executions.save(
                replace(
                    item,
                    status=status,
                    completed_at=completed_at or utcnow(),
                    result=result,
                    failure_summary=summary,
                )
            )
            self.outbox.append_event(
                f"schedule_execution.{status}",
                "schedule_execution",
                saved.id,
                {"schedule_execution_id": saved.id, "schedule_id": saved.schedule_id},
            )
            reconciled += 1
        self.transaction.commit()
        return {"reconciled": reconciled}

    def _current_state(self, item: ScheduleExecutionDTO) -> tuple[str, datetime | None, dict[str, Any] | None, str | None]:
        if item.flow_execution_id:
            flow_execution = self.flow_executions.get(item.flow_execution_id)
            if flow_execution is not None:
                return flow_execution.status, flow_execution.completed_at, flow_execution.output, flow_execution.failure_summary
        if item.execution_id:
            execution = self.executions.get(item.execution_id)
            if execution is not None:
                return execution.status, execution.completed_at, execution.result, execution.failure_summary
        return item.status, item.completed_at, item.result, item.failure_summary


class TriggerScheduleManually:
    def __init__(self, schedules: ScheduleRepository, executions: ScheduleExecutionRepository, creator: ScheduleExecutionCreator, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.schedules = schedules
        self.executions = executions
        self.creator = creator
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, schedule_id: int, *, actor: ActorDTO) -> ScheduleExecutionDTO:
        schedule = _require_schedule(self.schedules, schedule_id)
        scheduled_for = utcnow()
        execution = self.executions.add(ScheduleExecutionDTO(id=new_id("sex"), schedule_id=schedule_id, scheduled_for=scheduled_for, status="created", trigger_type="manual", execution_id=None, flow_execution_id=None, started_at=None, completed_at=None, result=None, failure_summary=None, created_at=scheduled_for))
        result = self.creator.create_execution(schedule, execution, actor)
        saved = self.executions.save(replace(execution, status="running", execution_id=result.get("execution_id"), flow_execution_id=result.get("flow_execution_id"), started_at=scheduled_for, result=result))
        self.outbox.append_event("schedule.triggered_manually", "schedule", str(schedule_id), {"schedule_id": schedule_id, "schedule_execution_id": saved.id})
        _audit(self.audit, actor, "schedule.triggered_manually", "schedule", str(schedule_id), after={"schedule_execution_id": saved.id})
        self.transaction.commit()
        return saved


class CalculateNextScheduleRun:
    def execute(self, schedule: ScheduleDTO, after: datetime | None = None) -> datetime | None:
        return _next_run(schedule, after or utcnow())


ApplyOverlapPolicy = TriggerDueSchedules
HandleScheduleMisfire = TriggerDueSchedules


def _trigger_one(schedule: ScheduleDTO, scheduled_for: datetime, now: datetime, executions: ScheduleExecutionRepository, creator: ScheduleExecutionCreator, outbox: OutboxPort) -> ScheduleExecutionDTO:
    existing = executions.get_by_schedule_time(int(schedule.id), scheduled_for)
    if existing is not None:
        return existing
    if _is_misfire(schedule, scheduled_for, now) and schedule.misfire_policy == "skip":
        skipped = executions.add(ScheduleExecutionDTO(id=new_id("sex"), schedule_id=int(schedule.id), scheduled_for=scheduled_for, status="skipped", trigger_type="scheduled", execution_id=None, flow_execution_id=None, started_at=None, completed_at=now, result={"reason": "misfire_skip"}, failure_summary=None, created_at=now))
        outbox.append_event("schedule.skipped", "schedule", str(schedule.id), {"schedule_id": schedule.id, "schedule_execution_id": skipped.id, "reason": "misfire"})
        return skipped
    if schedule.overlap_policy == "forbid" and executions.active_for_schedule(int(schedule.id)):
        skipped = executions.add(ScheduleExecutionDTO(id=new_id("sex"), schedule_id=int(schedule.id), scheduled_for=scheduled_for, status="skipped", trigger_type="scheduled", execution_id=None, flow_execution_id=None, started_at=None, completed_at=now, result={"reason": "overlap_forbid"}, failure_summary=None, created_at=now))
        outbox.append_event("schedule.skipped", "schedule", str(schedule.id), {"schedule_id": schedule.id, "schedule_execution_id": skipped.id, "reason": "overlap_forbid"})
        return skipped
    created = executions.add(ScheduleExecutionDTO(id=new_id("sex"), schedule_id=int(schedule.id), scheduled_for=scheduled_for, status="created", trigger_type="scheduled", execution_id=None, flow_execution_id=None, started_at=None, completed_at=None, result=None, failure_summary=None, created_at=now))
    result = creator.create_execution(schedule, created, ActorDTO(actor_type="system"))
    saved = executions.save(replace(created, status="running", execution_id=result.get("execution_id"), flow_execution_id=result.get("flow_execution_id"), started_at=now, result=result))
    outbox.append_event("schedule.triggered", "schedule", str(schedule.id), {"schedule_id": schedule.id, "schedule_execution_id": saved.id})
    return saved


def _record_trigger_failure(
    schedule: ScheduleDTO,
    scheduled_for: datetime,
    now: datetime,
    executions: ScheduleExecutionRepository,
    outbox: OutboxPort,
    failure_summary: str,
) -> ScheduleExecutionDTO:
    existing = executions.get_by_schedule_time(int(schedule.id), scheduled_for)
    if existing is not None:
        saved = executions.save(replace(existing, status="failed", completed_at=now, failure_summary=failure_summary))
    else:
        saved = executions.add(
            ScheduleExecutionDTO(
                id=new_id("sex"),
                schedule_id=int(schedule.id),
                scheduled_for=scheduled_for,
                status="failed",
                trigger_type="scheduled",
                execution_id=None,
                flow_execution_id=None,
                started_at=None,
                completed_at=now,
                result={"error": failure_summary},
                failure_summary=failure_summary,
                created_at=now,
            )
        )
    outbox.append_event("schedule_execution.failed", "schedule_execution", saved.id, {"schedule_id": schedule.id, "schedule_execution_id": saved.id})
    return saved


def _advance_schedule(schedule: ScheduleDTO, scheduled_for: datetime, now: datetime) -> ScheduleDTO:
    next_run = _next_run(schedule, scheduled_for)
    status = "completed" if schedule.is_one_time or next_run is None else schedule.status
    is_active = False if status == "completed" else schedule.is_active
    return replace(schedule, next_run_at=next_run, last_run_at=now, last_dispatched_at=now, status=status, is_active=is_active)


def _schedule_from_payload(payload: dict[str, Any], *, actor: ActorDTO, existing: ScheduleDTO | None) -> ScheduleDTO:
    now = utcnow()
    recurrence_type = str(payload.get("recurrence_type") or (existing.recurrence_type if existing else "daily"))
    time_of_day = str(payload.get("time_of_day") or (existing.time_of_day if existing else "08:00"))
    weekdays = payload.get("weekdays", existing.weekdays if existing else None)
    day_of_month = payload.get("day_of_month", existing.day_of_month if existing else None)
    specific_date = payload.get("specific_date", existing.specific_date if existing else None)
    if isinstance(specific_date, str) and specific_date:
        specific_date = date.fromisoformat(specific_date)
    schedule_type = str(payload.get("schedule_type") or ("once" if recurrence_type == "once" else "cron"))
    interval_seconds = payload.get("interval_seconds", existing.interval_seconds if existing else None)
    cron_expression = payload.get("cron_expression")
    if not cron_expression and schedule_type != "interval":
        cron_expression = build_cron_expression(RecurrenceInput(recurrence_type=recurrence_type, time_of_day=time_of_day, weekdays=weekdays, day_of_month=day_of_month, specific_date=specific_date))
    timezone = str(payload.get("timezone") or (existing.timezone if existing else DEFAULT_TIMEZONE))
    target_type = str(payload.get("target_type") or ("flow" if payload.get("flow_version_id") else (existing.target_type if existing else "automation")))
    if target_type not in {"automation", "flow"}:
        raise ValueError("target_type must be 'automation' or 'flow'.")
    automation_id = payload.get("automation_id", existing.automation_id if existing else None)
    automation_version_id = payload.get("automation_version_id", existing.automation_version_id if existing else None)
    flow_id = payload.get("flow_id", existing.flow_id if existing else None)
    flow_version_id = payload.get("flow_version_id", existing.flow_version_id if existing else None)
    if target_type == "automation" and automation_id is None and automation_version_id is None:
        raise ValueError("Automation schedule requires automation_id or automation_version_id.")
    if target_type == "flow" and flow_version_id is None:
        raise ValueError("Flow schedule requires flow_version_id.")
    next_base = existing.last_run_at or now if existing else now
    draft = ScheduleDTO(
        id=existing.id if existing else None,
        key=payload.get("key", existing.key if existing else None),
        name=payload.get("name", existing.name if existing else None),
        automation_id=automation_id,
        automation_version_id=automation_version_id,
        flow_id=flow_id,
        flow_version_id=flow_version_id,
        target_type=target_type,
        cron_expression=cron_expression,
        timezone=timezone,
        is_active=bool(payload.get("is_active", existing.is_active if existing else True)),
        status=str(payload.get("status") or (existing.status if existing else "active")),
        schedule_type=schedule_type,
        recurrence_type=recurrence_type,
        time_of_day=time_of_day,
        weekdays=weekdays,
        day_of_month=day_of_month,
        specific_date=specific_date,
        interval_seconds=interval_seconds,
        is_one_time=recurrence_type == "once" or schedule_type == "once",
        payload=payload.get("payload", existing.payload if existing else {}) or {},
        misfire_policy=str(payload.get("misfire_policy") or (existing.misfire_policy if existing else "run_once_now")),
        max_catch_up_runs=int(payload.get("max_catch_up_runs") or (existing.max_catch_up_runs if existing else 1)),
        misfire_grace_seconds=int(payload.get("misfire_grace_seconds") or (existing.misfire_grace_seconds if existing else 3600)),
        overlap_policy=str(payload.get("overlap_policy") or (existing.overlap_policy if existing else "forbid")),
        next_run_at=None,
        last_run_at=existing.last_run_at if existing else None,
        last_dispatched_at=existing.last_dispatched_at if existing else None,
        created_by=existing.created_by if existing else actor.actor_id,
        created_at=existing.created_at if existing else None,
        updated_at=existing.updated_at if existing else None,
        paused_at=existing.paused_at if existing else None,
        archived_at=existing.archived_at if existing else None,
    )
    requested_next_run = payload.get("next_run_at")
    if isinstance(requested_next_run, str) and requested_next_run:
        requested_next_run = datetime.fromisoformat(requested_next_run.replace("Z", "+00:00"))
    return replace(draft, next_run_at=requested_next_run or _next_run(draft, next_base))


def _next_run(schedule: ScheduleDTO, after: datetime) -> datetime | None:
    return calculate_next_run(
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        after=after,
        recurrence_type=schedule.recurrence_type,
        time_of_day=schedule.time_of_day,
        specific_date=schedule.specific_date,
        interval_seconds=schedule.interval_seconds,
    )


def _is_misfire(schedule: ScheduleDTO, scheduled_for: datetime, now: datetime) -> bool:
    return aware(scheduled_for) + timedelta(seconds=schedule.misfire_grace_seconds) < aware(now)


def _require_schedule(schedules: ScheduleRepository, schedule_id: int) -> ScheduleDTO:
    schedule = schedules.get(schedule_id)
    if schedule is None:
        raise ValueError("Schedule not found.")
    return schedule


def _audit(audit_repo, actor: ActorDTO, action: str, resource_type: str, resource_id: str, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None) -> None:
    if audit_repo is None:
        return
    audit_repo.append(AuditEvent(id=new_id("aud"), actor_type=actor.actor_type, actor_id=actor.actor_id, action=action, resource_type=resource_type, resource_id=resource_id, before=before, after=after, ip=actor.ip, user_agent=actor.user_agent, occurred_at=utcnow()))


def occurrences_for_schedule(schedule: ScheduleDTO, from_date: date, to_date: date, now: datetime) -> list[dict[str, Any]]:
    tz = timezone_or_default(schedule.timezone)
    current = aware(now).astimezone(tz)
    start = datetime.combine(from_date, time.min, tzinfo=tz)
    end = datetime.combine(to_date, time.max, tzinfo=tz)
    if schedule.schedule_type == "interval":
        return []
    if not schedule.cron_expression:
        return []
    occurrences: list[dict[str, Any]] = []
    iterator = croniter(schedule.cron_expression, start - timedelta(seconds=1))
    for _ in range(500):
        occurs_at = iterator.get_next(datetime)
        if occurs_at > end:
            break
        occurrences.append({"schedule_id": schedule.id, "automation_id": schedule.automation_id, "recurrence_type": schedule.recurrence_type, "occurs_at": occurs_at, "status": "upcoming" if occurs_at > current else "missed", "schedule_execution_id": None, "execution_id": None})
        if schedule.is_one_time:
            break
    return occurrences


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
