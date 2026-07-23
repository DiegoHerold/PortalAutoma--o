from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.automations = AutomationRepository(db)
        self.db = db
        self.permissions = PermissionService(db)
        self.schedules = ScheduleRepository(db)

    def list_schedules(self):
        return self.schedules.list_all()

    def create_schedule(self, user: User, payload: ScheduleCreate) -> Schedule:
        automation = self.automations.get(payload.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_create")
        schedule = self.schedules.create(Schedule(**payload.model_dump()))
        self.audit.record(
            "schedule_created",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(schedule.id),
            details=schedule.cron_expression,
        )
        self.db.commit()
        return schedule

    def update_schedule(self, user: User, schedule_id: int, payload: ScheduleUpdate) -> Schedule:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise ValueError("Schedule not found.")
        current_automation = self.automations.get(schedule.automation_id)
        if current_automation is None:
            raise ValueError("Automation not found.")
        new_automation = self.automations.get(payload.automation_id)
        if new_automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, current_automation.category_id, "can_edit")
        self.permissions.ensure_category_action(user, new_automation.category_id, "can_edit")
        for field, value in payload.model_dump().items():
            setattr(schedule, field, value)
        updated = self.schedules.update(schedule)
        self.audit.record(
            "schedule_updated",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(updated.id),
            details=updated.cron_expression,
        )
        self.db.commit()
        return updated

    def delete_schedule(self, user: User, schedule_id: int) -> None:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise ValueError("Schedule not found.")
        automation = self.automations.get(schedule.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_delete")
        self.audit.record(
            "schedule_deleted",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(schedule.id),
            details=schedule.cron_expression,
        )
        self.schedules.delete(schedule)
