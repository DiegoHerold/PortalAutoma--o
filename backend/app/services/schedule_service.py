from __future__ import annotations

from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.permission_service import PermissionService
from app.utils.datetime import utcnow
from modules.catalog.infrastructure.repositories import SqlAlchemyCatalogRepository
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.flows.infrastructure.adapters import build_flow_adapters
from modules.orchestration.infrastructure.repositories import SqlAlchemyExecutionRepository
from modules.orchestration.scheduling.application import (
    ArchiveSchedule,
    CreateSchedule,
    DisableSchedule,
    EnableSchedule,
    GetSchedule,
    GetScheduleExecution,
    GetScheduleHistory,
    ListSchedules,
    PauseSchedule,
    TriggerScheduleManually,
    UpdateSchedule,
    occurrences_for_schedule,
)
from modules.orchestration.scheduling.application.dto import ScheduleDTO, ScheduleExecutionDTO, to_payload
from modules.orchestration.scheduling.infrastructure.adapters import ScheduleAdapters, build_schedule_adapters


_SCHEDULE_EXECUTION_STATUS_TO_OCCURRENCE_STATUS = {
    "created": "queued",
    "running": "running",
    "succeeded": "success",
    "partially_succeeded": "success",
    "failed": "failed",
    "timed_out": "failed",
    "cancelled": "cancelled",
    "skipped": "missed",
}


class ScheduleService:
    """
    Legacy HTTP contract adapter for /schedules.

    Schedule rules live in modules.orchestration.scheduling. This class only
    translates HTTP compatibility payloads, performs current Access checks, and
    delegates to modular use cases.
    """

    def __init__(self, db: Session) -> None:
        self.catalog = SqlAlchemyCatalogRepository(db)
        self.db = db
        self.permissions = PermissionService(db)

    def list_schedules(self, target_type: str = "automation") -> list[dict[str, Any]]:
        adapters = build_schedule_adapters(self.db)
        schedules = ListSchedules(adapters.schedules).execute(limit=500)
        if target_type != "all":
            schedules = [item for item in schedules if item.target_type == target_type]
        if target_type == "automation":
            schedules = [item for item in schedules if item.automation_id is not None and item.status != "archived"]
        return [_schedule_payload(item) for item in schedules]

    def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        return _schedule_payload(GetSchedule(adapters.schedules).execute(schedule_id))

    def get_calendar_occurrences(self, from_date: date, to_date: date) -> list[dict[str, Any]]:
        adapters = build_schedule_adapters(self.db)
        schedules = [
            item
            for item in ListSchedules(adapters.schedules).execute(limit=500)
            if item.target_type == "automation" and item.automation_id is not None and item.status != "archived"
        ]
        automations = {item.id: item for item in self.catalog.list_automations()}
        execution_repo = SqlAlchemyExecutionRepository(self.db)
        now = utcnow()

        occurrences: list[dict[str, Any]] = []
        for schedule in schedules:
            automation = automations.get(int(schedule.automation_id))
            if automation is None:
                continue
            history = GetScheduleHistory(adapters.executions).execute(int(schedule.id))
            for occurrence in occurrences_for_schedule(schedule, from_date, to_date, now):
                schedule_execution = _match_schedule_execution(history, occurrence["occurs_at"])
                occurrences.append(
                    _legacy_occurrence_payload(
                        occurrence,
                        automation_name=automation.name,
                        category_id=automation.category_id,
                        schedule_execution=schedule_execution,
                        execution_repo=execution_repo,
                    )
                )

        occurrences.sort(key=lambda item: item["occurs_at"])
        return occurrences

    def create_schedule(self, user: User, payload: ScheduleCreate) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        command = self._payload_to_module(payload)
        self._ensure_payload_action(user, command, "can_create")
        schedule = CreateSchedule(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(
            command,
            actor=_actor(user),
        )
        return _schedule_payload(schedule)

    def update_schedule(self, user: User, schedule_id: int, payload: ScheduleUpdate) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        current = GetSchedule(adapters.schedules).execute(schedule_id)
        self._ensure_schedule_action(user, current, "can_edit")
        command = self._payload_to_module(payload, existing=current)
        self._ensure_payload_action(user, command, "can_edit")
        schedule = UpdateSchedule(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(
            schedule_id,
            command,
            actor=_actor(user),
        )
        return _schedule_payload(schedule)

    def delete_schedule(self, user: User, schedule_id: int) -> None:
        self.archive_schedule(user, schedule_id, action="can_delete")

    def enable_schedule(self, user: User, schedule_id: int) -> dict[str, Any]:
        return self._mutate_schedule(user, schedule_id, "can_edit", EnableSchedule)

    def pause_schedule(self, user: User, schedule_id: int) -> dict[str, Any]:
        return self._mutate_schedule(user, schedule_id, "can_edit", PauseSchedule)

    def disable_schedule(self, user: User, schedule_id: int) -> dict[str, Any]:
        return self._mutate_schedule(user, schedule_id, "can_edit", DisableSchedule)

    def archive_schedule(self, user: User, schedule_id: int, action: str = "can_delete") -> dict[str, Any]:
        return self._mutate_schedule(user, schedule_id, action, ArchiveSchedule)

    def trigger_schedule(self, user: User, schedule_id: int) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        schedule = GetSchedule(adapters.schedules).execute(schedule_id)
        self._ensure_schedule_action(user, schedule, "can_execute")
        execution = TriggerScheduleManually(
            adapters.schedules,
            adapters.executions,
            adapters.creator,
            adapters.outbox,
            adapters.audit,
            adapters.transaction,
        ).execute(schedule_id, actor=_actor(user))
        return to_payload(execution)

    def get_history(self, schedule_id: int) -> list[dict[str, Any]]:
        adapters = build_schedule_adapters(self.db)
        GetSchedule(adapters.schedules).execute(schedule_id)
        return [to_payload(item) for item in GetScheduleHistory(adapters.executions).execute(schedule_id)]

    def get_schedule_execution(self, schedule_execution_id: str) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        return to_payload(GetScheduleExecution(adapters.executions).execute(schedule_execution_id))

    def _mutate_schedule(
        self,
        user: User,
        schedule_id: int,
        action: str,
        use_case: Callable[[Any, Any, Any, Any], Any],
    ) -> dict[str, Any]:
        adapters = build_schedule_adapters(self.db)
        current = GetSchedule(adapters.schedules).execute(schedule_id)
        self._ensure_schedule_action(user, current, action)
        schedule = use_case(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(
            schedule_id,
            actor=_actor(user),
        )
        return _schedule_payload(schedule)

    def _payload_to_module(self, payload: ScheduleCreate | ScheduleUpdate, existing: ScheduleDTO | None = None) -> dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        if "payload" in data:
            data["payload"] = data.get("payload") or {}
        elif existing is None:
            data["payload"] = {}
        data["target_type"] = data.get("target_type") or (existing.target_type if existing else "automation")
        if data["target_type"] == "automation" and data.get("automation_version_id") and not data.get("automation_id"):
            version = self.catalog.get_version(int(data["automation_version_id"]))
            if version is None:
                raise ValueError("AutomationVersion not found.")
            data["automation_id"] = version.automation_id
        if data["target_type"] == "flow":
            flow_version_id = data.get("flow_version_id") or (existing.flow_version_id if existing else None)
            if not flow_version_id:
                raise ValueError("FlowVersion not found.")
            flow_adapters = build_flow_adapters(self.db)
            version = flow_adapters.versions.get(str(flow_version_id))
            if version is None:
                raise ValueError("FlowVersion not found.")
            data["flow_version_id"] = flow_version_id
            data["flow_id"] = data.get("flow_id") or version.flow_id
        return data

    def _ensure_payload_action(self, user: User, payload: dict[str, Any], action: str) -> None:
        if payload.get("target_type") == "flow":
            flow_id = payload.get("flow_id")
            if flow_id:
                flow = build_flow_adapters(self.db).flows.get(str(flow_id))
                if flow and flow.category_id is not None:
                    self.permissions.ensure_category_action(user, flow.category_id, action)
            return
        automation_id = payload.get("automation_id")
        if automation_id is not None:
            self.permissions.ensure_automation_action(user, int(automation_id), action)

    def _ensure_schedule_action(self, user: User, schedule: ScheduleDTO, action: str) -> None:
        if schedule.target_type == "flow":
            if schedule.flow_id:
                flow = build_flow_adapters(self.db).flows.get(schedule.flow_id)
                if flow and flow.category_id is not None:
                    self.permissions.ensure_category_action(user, flow.category_id, action)
            return
        if schedule.automation_id is not None:
            self.permissions.ensure_automation_action(user, schedule.automation_id, action)


def _schedule_payload(schedule: ScheduleDTO) -> dict[str, Any]:
    return {
        "id": schedule.id,
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
        "recurrence_type": schedule.recurrence_type,
        "time_of_day": schedule.time_of_day,
        "weekdays": schedule.weekdays,
        "day_of_month": schedule.day_of_month,
        "specific_date": schedule.specific_date,
        "is_one_time": schedule.is_one_time,
        "last_dispatched_at": schedule.last_dispatched_at,
        "status": schedule.status,
        "schedule_type": schedule.schedule_type,
        "interval_seconds": schedule.interval_seconds,
        "payload": schedule.payload,
        "misfire_policy": schedule.misfire_policy,
        "max_catch_up_runs": schedule.max_catch_up_runs,
        "misfire_grace_seconds": schedule.misfire_grace_seconds,
        "overlap_policy": schedule.overlap_policy,
        "next_run_at": schedule.next_run_at,
        "last_run_at": schedule.last_run_at,
        "paused_at": schedule.paused_at,
        "archived_at": schedule.archived_at,
    }


def _legacy_occurrence_payload(
    occurrence: dict[str, Any],
    *,
    automation_name: str,
    category_id: int | None,
    schedule_execution: ScheduleExecutionDTO | None,
    execution_repo: SqlAlchemyExecutionRepository,
) -> dict[str, Any]:
    status = occurrence["status"]
    execution_id = None
    schedule_execution_id = None
    if schedule_execution is not None:
        execution_status = _current_execution_status(schedule_execution, execution_repo)
        status = _SCHEDULE_EXECUTION_STATUS_TO_OCCURRENCE_STATUS.get(execution_status, status)
        execution_id = schedule_execution.execution_id
        schedule_execution_id = schedule_execution.id
    return {
        "schedule_id": occurrence["schedule_id"],
        "automation_id": occurrence["automation_id"],
        "automation_name": automation_name,
        "category_id": category_id,
        "recurrence_type": occurrence["recurrence_type"],
        "occurs_at": occurrence["occurs_at"].isoformat(),
        "status": status,
        "job_id": None,
        "execution_id": execution_id,
        "schedule_execution_id": schedule_execution_id,
    }


def _match_schedule_execution(history: list[ScheduleExecutionDTO], occurs_at) -> ScheduleExecutionDTO | None:
    for item in history:
        if item.scheduled_for == occurs_at:
            return item
        if item.scheduled_for.isoformat() == occurs_at.isoformat():
            return item
    return None


def _current_execution_status(schedule_execution: ScheduleExecutionDTO, execution_repo: SqlAlchemyExecutionRepository) -> str:
    if schedule_execution.execution_id:
        execution = execution_repo.get(schedule_execution.execution_id)
        if execution is not None:
            return execution.status
    return schedule_execution.status


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)
