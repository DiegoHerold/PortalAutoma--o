from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.schedule import ScheduleCreate, ScheduleOccurrence, ScheduleRead, ScheduleUpdate
from app.services.schedule_service import ScheduleService

router = APIRouter()
schedule_executions_router = APIRouter()


@router.get("")
def list_schedules(
    target_type: str = Query("automation", description="automation, flow ou all."),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[ScheduleRead]:
    return ScheduleService(db).list_schedules(target_type=target_type)


@router.get("/calendar")
def get_calendar_occurrences(
    from_date: date = Query(..., description="Inicio do intervalo (inclusive)."),
    to_date: date = Query(..., description="Fim do intervalo (inclusive)."),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[ScheduleOccurrence]:
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date deve ser maior ou igual a from_date.")
    return ScheduleService(db).get_calendar_occurrences(from_date, to_date)


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).get_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).create_schedule(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).update_schedule(current_user, schedule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def patch_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).update_schedule(current_user, schedule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        ScheduleService(db).delete_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/enable", response_model=ScheduleRead)
def enable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).enable_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/pause", response_model=ScheduleRead)
def pause_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).pause_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/disable", response_model=ScheduleRead)
def disable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).disable_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/archive", response_model=ScheduleRead)
def archive_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ScheduleRead:
    try:
        return ScheduleService(db).archive_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/trigger")
def trigger_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    try:
        return ScheduleService(db).trigger_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{schedule_id}/history")
def get_schedule_history(
    schedule_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[dict]:
    try:
        return ScheduleService(db).get_history(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@schedule_executions_router.get("/{schedule_execution_id}")
def get_schedule_execution(
    schedule_execution_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    try:
        return ScheduleService(db).get_schedule_execution(schedule_execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
