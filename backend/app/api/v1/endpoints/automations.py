from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.automation import AutomationCreate, AutomationRead, AutomationUpdate
from app.services.automation_service import AutomationService

router = APIRouter()


@router.get("", response_model=list[AutomationRead])
def list_automations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[AutomationRead]:
    return AutomationService(db).list_automations(current_user)


@router.get("/{automation_id}", response_model=AutomationRead)
def get_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationRead:
    try:
        return AutomationService(db).get_automation(current_user, automation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
def create_automation(
    payload: AutomationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationRead:
    return AutomationService(db).create_automation(current_user, payload)


@router.put("/{automation_id}", response_model=AutomationRead)
def update_automation(
    automation_id: int,
    payload: AutomationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationRead:
    try:
        return AutomationService(db).update_automation(current_user, automation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        AutomationService(db).delete_automation(current_user, automation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
