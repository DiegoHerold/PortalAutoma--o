from sqlalchemy.orm import Session

from app.core.permissions import is_admin
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.execution_repository import ExecutionRepository


class ExecutionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.executions = ExecutionRepository(db)
        self.automations = AutomationRepository(db)

    def list_executions(self, user: User):
        executions = self.executions.list_all()
        if is_admin(user):
            return executions

        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        jobs_automation_ids = {execution.job.automation_id for execution in executions if execution.job}
        automation_category_map = {
            automation.id: automation.category_id
            for automation in self.automations.list_all()
            if automation.id in jobs_automation_ids
        }
        return [
            execution
            for execution in executions
            if automation_category_map.get(execution.job.automation_id) in allowed_category_ids
        ]

    def get_execution(self, user: User, execution_id: int):
        execution = self.executions.get(execution_id)
        if execution is None:
            raise ValueError("Execution not found.")
        if is_admin(user):
            return execution
        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        automation = self.automations.get(execution.job.automation_id)
        if automation is None or automation.category_id not in allowed_category_ids:
            raise ValueError("Execution not found.")
        return execution
