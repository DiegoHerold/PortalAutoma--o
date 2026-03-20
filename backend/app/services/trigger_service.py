from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trigger import Trigger
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.trigger_repository import TriggerRepository
from app.schemas.job import JobCreate
from app.schemas.trigger import TriggerCreate
from app.services.job_dispatcher_service import JobDispatcherService
from app.services.permission_service import PermissionService


class TriggerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.triggers = TriggerRepository(db)
        self.automations = AutomationRepository(db)
        self.permissions = PermissionService(db)

    def list_triggers(self) -> list[Trigger]:
        return self.triggers.list_all()

    def create_trigger(self, user: User, payload: TriggerCreate) -> Trigger:
        automation = self.automations.get(payload.automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_create")
        return self.triggers.create(Trigger(**payload.model_dump()))

    def dispatch_by_route(self, route_path: str, secret_token: str, payload_json: dict) -> int:
        trigger = self.triggers.get_by_route_path(route_path)
        if trigger is None or not trigger.is_active or trigger.secret_token != secret_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger credentials.")

        automation = self.automations.get(trigger.automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")

        job = JobDispatcherService(self.db).dispatch_system(
            JobCreate(
                automation_id=automation.id,
                priority=automation.default_priority,
                payload_json=payload_json,
            )
        )
        return job.id
