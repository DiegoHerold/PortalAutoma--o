from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.worker import WorkerCreate, WorkerRead, WorkerUpdate
from app.services.worker_service import WorkerService

router = APIRouter()


@router.get("/installer-config")
def installer_config(_=Depends(get_current_user)) -> dict:
    """
    Address the Automation Agent installer should use to reach this server.
    Always derived from BACKEND_PUBLIC_URL (backend/.env) — never from the
    browser's own URL — so a worker on a different machine gets the real
    server address regardless of which host the admin happened to browse
    from. Changing machines/networks is a single .env edit + backend
    restart, nothing to rebuild or hunt for in code.
    """
    settings = get_settings()
    base = settings.backend_public_url.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return {
        "central_api_url": f"{base}/api",
        "central_websocket_url": f"{ws_base}/api/v1/agents/ws",
    }


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


@router.post("", response_model=WorkerRead, status_code=status.HTTP_201_CREATED)
def create_worker(
    payload: WorkerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> WorkerRead:
    try:
        return WorkerService(db).create_worker(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{worker_id}", response_model=WorkerRead)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> WorkerRead:
    try:
        return WorkerService(db).update_worker(current_user, worker_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        WorkerService(db).delete_worker(current_user, worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
