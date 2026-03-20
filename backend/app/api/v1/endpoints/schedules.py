from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.schedule import ScheduleRead
from app.services.schedule_service import ScheduleService

router = APIRouter()


@router.get("")
def list_schedules(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[ScheduleRead]:
    return ScheduleService(db).list_schedules()
