from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.job import JobCreate, JobRead
from app.services.job_dispatcher_service import JobDispatcherService, JobNotCancellableError
from app.services.job_enrichment_service import JobEnrichmentService

router = APIRouter()


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[JobRead]:
    """List jobs with enriched data (ETA, queue position, etc.)."""
    dispatcher = JobDispatcherService(db)
    enrichment = JobEnrichmentService(db)
    
    jobs = dispatcher.list_jobs(current_user)
    return enrichment.enrich_jobs(jobs)


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> JobRead:
    """Get a job with enriched data (ETA, queue position, etc.)."""
    try:
        dispatcher = JobDispatcherService(db)
        enrichment = JobEnrichmentService(db)
        
        job = dispatcher.get_job(current_user, job_id)
        return enrichment.enrich_job(job)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def dispatch_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> JobRead:
    """Dispatch a new job."""
    dispatcher = JobDispatcherService(db)
    enrichment = JobEnrichmentService(db)
    
    job = dispatcher.dispatch(current_user, payload)
    return enrichment.enrich_job(job)


@router.post("/{job_id}:cancel", response_model=JobRead)
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> JobRead:
    """Cancel a job that is still pending, queued, or running."""
    dispatcher = JobDispatcherService(db)
    enrichment = JobEnrichmentService(db)
    try:
        job = dispatcher.cancel_job(current_user, job_id)
    except JobNotCancellableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return enrichment.enrich_job(job)
