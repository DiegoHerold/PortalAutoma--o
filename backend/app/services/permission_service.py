from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.constants import GlobalRoleSlug
from app.core.permissions import can_access_category
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository


class PermissionService:
    def __init__(self, db: Session) -> None:
        self.automations = AutomationRepository(db)

    def ensure_category_action(self, user: User, category_id: int, action: str) -> None:
        if not can_access_category(user, category_id, action, user.category_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this category.",
            )

    def ensure_admin_or_manager(self, user: User) -> None:
        if user.role.slug not in {GlobalRoleSlug.ADMIN, GlobalRoleSlug.MANAGER}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires elevated privileges.",
            )

    def ensure_automation_action(self, user: User, automation_id: int, action: str) -> int:
        automation = self.automations.get(automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        self.ensure_category_action(user, automation.category_id, action)
        return automation.category_id
