from sqlalchemy.orm import Session

from app.models.automation_worker_preference import AutomationWorkerPreference
from app.models.user import User
from app.repositories.automation_worker_preference_repository import AutomationWorkerPreferenceRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas.worker_preference import WorkerPreferenceItem, WorkerPreferenceResponse
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class WorkerPreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.preferences = AutomationWorkerPreferenceRepository(db)
        self.workers = WorkerRepository(db)
        self.audit = AuditService(db)
        self.permissions = PermissionService(db)

    def get_for_automation(self, automation_id: int, category_id: int) -> list[WorkerPreferenceResponse]:
        preferences = self.preferences.get_by_automation(automation_id)
        worker_map = {w.id: w.name for w in self.workers.list_all()}
        
        return [
            WorkerPreferenceResponse(
                worker_id=pref.worker_id,
                worker_name=worker_map.get(pref.worker_id, "Unknown"),
                priority_order=pref.priority_order,
                is_active=pref.is_active,
            )
            for pref in preferences
        ]

    def replace_for_automation(
        self, 
        user: User, 
        automation_id: int, 
        category_id: int, 
        items: list[WorkerPreferenceItem]
    ) -> list[WorkerPreferenceResponse]:
        self.permissions.ensure_category_action(user, category_id, "can_edit")
        
        # Delete existing preferences
        self.preferences.delete_by_automation(automation_id)
        
        # Create new preferences
        new_preferences = [
            AutomationWorkerPreference(
                automation_id=automation_id,
                worker_id=item.worker_id,
                priority_order=item.priority_order,
                is_active=True,
            )
            for item in items
        ]
        
        if new_preferences:
            self.preferences.create_many(new_preferences)
        
        self.audit.record(
            "worker_preferences_updated",
            actor_email=user.email,
            resource_type="automation",
            resource_id=str(automation_id),
            details=f"Updated {len(items)} worker preferences",
        )
        
        self.db.commit()
        
        return self.get_for_automation(automation_id, category_id)
