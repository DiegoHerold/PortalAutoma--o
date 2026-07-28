from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from modules.fleet.application.dto import AutomationWorkerPreferenceDTO
from modules.fleet.infrastructure.orm.models import AutomationWorkerPreferenceRecord, FleetWorkerRecord


class SqlAlchemyAutomationWorkerPreferenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_automation(self, automation_id: int) -> list[AutomationWorkerPreferenceDTO]:
        rows = self.db.execute(
            select(AutomationWorkerPreferenceRecord, FleetWorkerRecord.name.label("worker_name"))
            .join(FleetWorkerRecord, FleetWorkerRecord.id == AutomationWorkerPreferenceRecord.worker_id)
            .where(AutomationWorkerPreferenceRecord.automation_id == automation_id)
            .order_by(AutomationWorkerPreferenceRecord.priority_order)
        ).all()
        return [
            AutomationWorkerPreferenceDTO(
                worker_id=record.worker_id,
                worker_name=worker_name,
                priority_order=record.priority_order,
                is_active=record.is_active,
            )
            for record, worker_name in rows
        ]

    def replace_for_automation(self, automation_id: int, preferences: list[dict]) -> list[AutomationWorkerPreferenceDTO]:
        self.db.execute(delete(AutomationWorkerPreferenceRecord).where(AutomationWorkerPreferenceRecord.automation_id == automation_id))
        for item in preferences:
            self.db.add(
                AutomationWorkerPreferenceRecord(
                    automation_id=automation_id,
                    worker_id=int(item["worker_id"]),
                    priority_order=int(item["priority_order"]),
                    is_active=True,
                )
            )
        self.db.flush()
        return self.list_for_automation(automation_id)
