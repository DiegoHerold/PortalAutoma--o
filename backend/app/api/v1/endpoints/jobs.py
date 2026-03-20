from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.job import JobCreate, JobRead
from app.services.job_dispatcher_service import JobDispatcherService

router = APIRouter()


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[JobRead]:
    return JobDispatcherService(db).list_jobs(current_user)


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> JobRead:
    try:
        return JobDispatcherService(db).get_job(current_user, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def dispatch_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> JobRead:
    return JobDispatcherService(db).dispatch(current_user, payload)
