from sqlalchemy.orm import Session

from app.core.permissions import is_admin
from app.models.automation import Automation
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.schemas.automation import AutomationCreate
from app.schemas.automation import AutomationUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class AutomationService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.automations = AutomationRepository(db)
        self.permissions = PermissionService(db)

    def list_automations(self, user: User) -> list[Automation]:
        automations = self.automations.list_all()
        if is_admin(user):
            return automations

        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        return [automation for automation in automations if automation.category_id in allowed_category_ids]

    def create_automation(self, user: User, payload: AutomationCreate) -> Automation:
        self.permissions.ensure_category_action(user, payload.category_id, "can_create")
        automation = Automation(**payload.model_dump())
        automation = self.automations.create(automation)
        self.audit.record(
            "automation_created",
            actor_email=user.email,
            resource_type="automation",
            resource_id=str(automation.id),
            details=automation.slug,
        )
        self.db.commit()
        return automation

    def update_automation(self, user: User, automation_id: int, payload: AutomationUpdate) -> Automation:
        automation = self.automations.get(automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_edit")
        for field, value in payload.model_dump().items():
            setattr(automation, field, value)
        automation = self.automations.update(automation)
        self.audit.record(
            "automation_updated",
            actor_email=user.email,
            resource_type="automation",
            resource_id=str(automation.id),
            details=automation.slug,
        )
        self.db.commit()
        return automation

    def delete_automation(self, user: User, automation_id: int) -> None:
        automation = self.automations.get(automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_delete")
        self.audit.record(
            "automation_deleted",
            actor_email=user.email,
            resource_type="automation",
            resource_id=str(automation.id),
            details=automation.slug,
        )
        self.automations.delete(automation)

    def get_automation(self, user: User, automation_id: int) -> Automation:
        automation = self.automations.get(automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        if is_admin(user):
            return automation
        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        if automation.category_id not in allowed_category_ids:
            raise ValueError("Automation not found.")
        return automation
