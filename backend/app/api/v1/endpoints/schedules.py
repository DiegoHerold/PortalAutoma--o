from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services.schedule_service import ScheduleService

router = APIRouter()


@router.get("")
def list_schedules(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[ScheduleRead]:
    return ScheduleService(db).list_schedules()


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


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        ScheduleService(db).delete_schedule(current_user, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
