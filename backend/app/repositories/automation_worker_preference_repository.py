from sqlalchemy.orm import Session

from app.models.automation_worker_preference import AutomationWorkerPreference


class AutomationWorkerPreferenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_automation(self, automation_id: int) -> list[AutomationWorkerPreference]:
        return (
            self.db.query(AutomationWorkerPreference)
            .filter(AutomationWorkerPreference.automation_id == automation_id)
            .order_by(AutomationWorkerPreference.priority_order)
            .all()
        )

    def get_active_by_automation(self, automation_id: int) -> list[AutomationWorkerPreference]:
        return (
            self.db.query(AutomationWorkerPreference)
            .filter(
                AutomationWorkerPreference.automation_id == automation_id,
                AutomationWorkerPreference.is_active == True,
            )
            .order_by(AutomationWorkerPreference.priority_order)
            .all()
        )

    def delete_by_automation(self, automation_id: int) -> None:
        self.db.query(AutomationWorkerPreference).filter(
            AutomationWorkerPreference.automation_id == automation_id
        ).delete()

    def create_many(self, preferences: list[AutomationWorkerPreference]) -> list[AutomationWorkerPreference]:
        self.db.add_all(preferences)
        self.db.flush()
        return preferences
