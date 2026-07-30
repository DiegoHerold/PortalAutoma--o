from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.authorization import ensure_automation_action, ensure_permission
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.scheduling.api.schemas import (
    ScheduleCalendarResponse,
    ScheduleCreateRequest,
    ScheduleExecutionResponse,
    SchedulePreviewRequest,
    SchedulePreviewResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)
from modules.orchestration.scheduling.application import (
    ArchiveSchedule,
    CalendarQueryError,
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
    build_schedule_calendar,
)
from modules.orchestration.scheduling.application.dto import ScheduleDTO, to_payload
from modules.orchestration.scheduling.domain import DEFAULT_TIMEZONE, RecurrenceError, RecurrenceInput, build_cron_expression, calculate_next_run
from modules.orchestration.scheduling.infrastructure.adapters import build_schedule_adapters

router = APIRouter()
schedule_executions_router = APIRouter()


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _split_csv_int(value: str | None) -> list[int] | None:
    items = _split_csv(value)
    if not items:
        return None
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Lista de ids invalida.") from exc


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


@router.get("/calendar", response_model=ScheduleCalendarResponse)
def get_schedule_calendar(
    date_from: date = Query(..., alias="from", description="Inicio do intervalo (inclusive)."),
    date_to: date = Query(..., alias="to", description="Fim do intervalo (inclusive)."),
    timezone: str = Query(DEFAULT_TIMEZONE, description="Timezone de exibicao (IANA)."),
    view: str = Query("month", description="month, week, day, agenda ou now (define o tamanho dos buckets de densidade)."),
    target_type: str = Query("all", description="automation, flow ou all."),
    automation_ids: str | None = Query(None, description="Lista de ids de automacao separados por virgula."),
    flow_ids: str | None = Query(None, description="Lista de ids de fluxo separados por virgula."),
    statuses: str | None = Query(None, description="Lista de temporal_status (ou aliases: running, failed, completed, future, past) separados por virgula."),
    owners: str | None = Query(None, description="Lista de created_by separados por virgula."),
    search: str | None = Query(None, description="Busca por nome do agendamento, automacao/fluxo ou responsavel."),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ScheduleCalendarResponse:
    ensure_permission(db, user, "schedule.read")
    try:
        result = build_schedule_calendar(
            db,
            date_from=date_from,
            date_to=date_to,
            display_timezone=timezone,
            view=view,
            target_type=target_type,
            automation_ids=_split_csv_int(automation_ids),
            flow_ids=_split_csv(flow_ids),
            statuses=_split_csv(statuses),
            owners=_split_csv(owners),
            search=search,
            now=datetime.now(UTC),
        )
    except CalendarQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduleCalendarResponse.model_validate(to_payload(result))


@router.post("/preview", response_model=SchedulePreviewResponse)
def preview_schedule_occurrences(
    payload: SchedulePreviewRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> SchedulePreviewResponse:
    """Calcula as proximas N ocorrencias de uma configuracao de recorrencia sem
    persistir nada — usado pelo formulario de criacao/edicao (secao 'Proximas execucoes')."""
    ensure_permission(db, user, "schedule.read")
    draft = ScheduleDTO(
        id=None,
        key=None,
        name=None,
        automation_id=None,
        automation_version_id=None,
        flow_id=None,
        flow_version_id=None,
        target_type="automation",
        cron_expression=payload.cron_expression,
        timezone=payload.timezone,
        is_active=True,
        status="active",
        schedule_type=payload.schedule_type or ("interval" if payload.interval_seconds else "cron"),
        recurrence_type=payload.recurrence_type,
        time_of_day=payload.time_of_day,
        weekdays=payload.weekdays,
        day_of_month=payload.day_of_month,
        specific_date=payload.specific_date,
        interval_seconds=payload.interval_seconds,
        is_one_time=payload.recurrence_type == "once",
        payload={},
        misfire_policy="run_once_now",
        max_catch_up_runs=1,
        misfire_grace_seconds=3600,
        overlap_policy="forbid",
        next_run_at=None,
        last_run_at=None,
        last_dispatched_at=None,
        created_by=None,
    )
    if not draft.cron_expression and draft.schedule_type != "interval":
        try:
            draft = replace(
                draft,
                cron_expression=build_cron_expression(
                    RecurrenceInput(
                        recurrence_type=draft.recurrence_type,
                        time_of_day=draft.time_of_day,
                        weekdays=draft.weekdays,
                        day_of_month=draft.day_of_month,
                        specific_date=draft.specific_date,
                    )
                ),
            )
        except RecurrenceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    occurrences: list[datetime] = []
    cursor = datetime.now(UTC)
    count = max(1, min(payload.count, 20))
    try:
        for _ in range(count):
            next_run = calculate_next_run(
                schedule_type=draft.schedule_type,
                cron_expression=draft.cron_expression,
                timezone=draft.timezone,
                after=cursor,
                recurrence_type=draft.recurrence_type,
                time_of_day=draft.time_of_day,
                specific_date=draft.specific_date,
                interval_seconds=draft.interval_seconds,
            )
            if next_run is None:
                break
            occurrences.append(next_run)
            cursor = next_run
    except RecurrenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SchedulePreviewResponse(occurrences=occurrences)


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
