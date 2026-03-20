from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.trigger import TriggerCreate, TriggerRead
from app.services.trigger_service import TriggerService

router = APIRouter()


@router.get("")
def list_triggers(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[TriggerRead]:
    return TriggerService(db).list_triggers()


@router.post("", response_model=TriggerRead, status_code=status.HTTP_201_CREATED)
def create_trigger(
    payload: TriggerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> TriggerRead:
    return TriggerService(db).create_trigger(current_user, payload)


@router.post("/invoke/{route_path}")
def invoke_trigger(
    route_path: str,
    payload_json: dict = Body(default={}),
    x_trigger_secret: str = Header(...),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    job_id = TriggerService(db).dispatch_by_route(route_path, x_trigger_secret, payload_json)
    return {"job_id": job_id}
