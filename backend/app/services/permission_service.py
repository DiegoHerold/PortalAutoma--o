from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.automation_repository import AutomationRepository
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.repositories import SqlAlchemyAccessRepository


class PermissionService:
    def __init__(self, db: Session) -> None:
        self.access = SqlAlchemyAccessRepository(db)
        self.automations = AutomationRepository(db)

    def ensure_category_action(self, user, category_id: int, action: str) -> None:
        try:
            PermissionChecker(self.access).ensure_category_action(user, category_id, action)
        except AuthorizationDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    def ensure_admin_or_manager(self, user) -> None:
        try:
            PermissionChecker(self.access).ensure_admin_or_manager(user)
        except AuthorizationDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    def ensure_automation_action(self, user, automation_id: int, action: str) -> int:
        automation = self.automations.get(automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        self.ensure_category_action(user, automation.category_id, action)
        return automation.category_id
