from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.worker import WorkerRead
from app.services.worker_service import WorkerService

router = APIRouter()


@router.get("", response_model=list[WorkerRead])
def list_workers(db: Session = Depends(get_db), _=Depends(get_current_user)) -> list[WorkerRead]:
    return WorkerService(db).list_workers()


@router.get("/{worker_id}", response_model=WorkerRead)
def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> WorkerRead:
    try:
        return WorkerService(db).get_worker(worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
