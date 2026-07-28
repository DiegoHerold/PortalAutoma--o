from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.execution import ExecutionRead
from app.services.execution_service import ExecutionService

router = APIRouter()


@router.get("")
def list_executions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[ExecutionRead]:
    return ExecutionService(db).list_executions(current_user)


@router.get("/{execution_id}", response_model=ExecutionRead)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ExecutionRead:
    try:
        return ExecutionService(db).get_execution(current_user, execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
