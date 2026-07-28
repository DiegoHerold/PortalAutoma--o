from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.authorization import ensure_automation_action, ensure_permission
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.scheduling.api.schemas import (
    ScheduleCreateRequest,
    ScheduleExecutionResponse,
    ScheduleOccurrenceResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)
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
from modules.orchestration.scheduling.application.dto import to_payload
from modules.orchestration.scheduling.infrastructure.adapters import build_schedule_adapters

router = APIRouter()
schedule_executions_router = APIRouter()


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    target_type: str = Query("automation", description="automation, flow ou all."),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[ScheduleResponse]:
    ensure_permission(db, user, "schedule.read")
    schedules = ListSchedules(build_schedule_adapters(db).schedules).execute(limit=500, offset=0)
    if target_type != "all":
        schedules = [item for item in schedules if item.target_type == target_type]
    return [ScheduleResponse.model_validate(to_payload(item)) for item in schedules]


@router.get("/calendar", response_model=list[ScheduleOccurrenceResponse])
def get_calendar_occurrences(
    from_date: date = Query(..., description="Inicio do intervalo (inclusive)."),
    to_date: date = Query(..., description="Fim do intervalo (inclusive)."),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[ScheduleOccurrenceResponse]:
    ensure_permission(db, user, "schedule.read")
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date deve ser maior ou igual a from_date.")
    catalog = build_catalog_adapters(db).catalog
    schedules = ListSchedules(build_schedule_adapters(db).schedules).execute(limit=500, offset=0)
    occurrences: list[ScheduleOccurrenceResponse] = []
    for schedule in schedules:
        for item in occurrences_for_schedule(schedule, from_date, to_date, datetime.now(UTC)):
            automation = catalog.get_automation(int(schedule.automation_id)) if schedule.automation_id else None
            occurrences.append(
                ScheduleOccurrenceResponse.model_validate(
                    {
                        **to_payload(item),
                        "automation_name": automation.name if automation else (schedule.name or ""),
                        "category_id": automation.category_id if automation else None,
                    }
                )
            )
    return occurrences


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleResponse:
    ensure_permission(db, user, "schedule.read")
    try:
        schedule = GetSchedule(build_schedule_adapters(db).schedules).execute(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.model_validate(to_payload(schedule))


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleResponse:
    _ensure_schedule_write(db, user, payload.automation_id)
    adapters = build_schedule_adapters(db)
    try:
        schedule = CreateSchedule(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(
            payload.model_dump(),
            actor=_actor(user, request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ScheduleResponse.model_validate(to_payload(schedule))


@router.put("/{schedule_id}", response_model=ScheduleResponse)
@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleResponse:
    current = _get_schedule_or_404(db, schedule_id)
    _ensure_schedule_write(db, user, payload.automation_id or current.automation_id)
    adapters = build_schedule_adapters(db)
    try:
        schedule = UpdateSchedule(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(
            schedule_id,
            payload.model_dump(exclude_unset=True),
            actor=_actor(user, request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.model_validate(to_payload(schedule))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_schedule(
    schedule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    _mutate_schedule_status(db, user, schedule_id, request, "archive")


@router.post("/{schedule_id}/enable", response_model=ScheduleResponse)
def enable_schedule(schedule_id: int, request: Request, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ScheduleResponse:
    return _mutate_schedule_status(db, user, schedule_id, request, "enable")


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
def pause_schedule(schedule_id: int, request: Request, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ScheduleResponse:
    return _mutate_schedule_status(db, user, schedule_id, request, "pause")


@router.post("/{schedule_id}/disable", response_model=ScheduleResponse)
def disable_schedule(schedule_id: int, request: Request, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ScheduleResponse:
    return _mutate_schedule_status(db, user, schedule_id, request, "disable")


@router.post("/{schedule_id}/archive", response_model=ScheduleResponse)
def archive_schedule(schedule_id: int, request: Request, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> ScheduleResponse:
    return _mutate_schedule_status(db, user, schedule_id, request, "archive")


@router.post("/{schedule_id}/trigger", response_model=ScheduleExecutionResponse)
def trigger_schedule(
    schedule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleExecutionResponse:
    schedule = _get_schedule_or_404(db, schedule_id)
    if schedule.automation_id:
        ensure_automation_action(db, user, int(schedule.automation_id), "can_execute")
    else:
        ensure_permission(db, user, "schedule.trigger")
    adapters = build_schedule_adapters(db)
    try:
        execution = TriggerScheduleManually(adapters.schedules, adapters.executions, adapters.creator, adapters.outbox, adapters.audit, adapters.transaction).execute(
            schedule_id,
            actor=_actor(user, request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleExecutionResponse.model_validate(to_payload(execution))


@router.get("/{schedule_id}/history", response_model=list[ScheduleExecutionResponse])
def get_schedule_history(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[ScheduleExecutionResponse]:
    ensure_permission(db, user, "schedule.read")
    adapters = build_schedule_adapters(db)
    return [ScheduleExecutionResponse.model_validate(to_payload(item)) for item in GetScheduleHistory(adapters.executions).execute(schedule_id)]


@schedule_executions_router.get("/{schedule_execution_id}", response_model=ScheduleExecutionResponse)
def get_schedule_execution(
    schedule_execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleExecutionResponse:
    ensure_permission(db, user, "schedule.read")
    try:
        execution = GetScheduleExecution(build_schedule_adapters(db).executions).execute(schedule_execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleExecutionResponse.model_validate(to_payload(execution))


def _mutate_schedule_status(
    db: Session,
    user: Any,
    schedule_id: int,
    request: Request,
    action: str,
) -> ScheduleResponse:
    schedule = _get_schedule_or_404(db, schedule_id)
    _ensure_schedule_write(db, user, schedule.automation_id)
    adapters = build_schedule_adapters(db)
    actor = _actor(user, request)
    use_case = {
        "enable": EnableSchedule,
        "pause": PauseSchedule,
        "disable": DisableSchedule,
        "archive": ArchiveSchedule,
    }[action]
    try:
        result = use_case(adapters.schedules, adapters.outbox, adapters.audit, adapters.transaction).execute(schedule_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.model_validate(to_payload(result))


def _get_schedule_or_404(db: Session, schedule_id: int):
    try:
        return GetSchedule(build_schedule_adapters(db).schedules).execute(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_schedule_write(db: Session, user: Any, automation_id: int | None) -> None:
    if automation_id is not None:
        ensure_automation_action(db, user, int(automation_id), "can_edit")
        return
    ensure_permission(db, user, "schedule.update")


def _actor(user: Any, request: Request) -> ActorDTO:
    return ActorDTO(
        actor_type="user",
        actor_id=str(user.id),
        actor_email=user.email,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
