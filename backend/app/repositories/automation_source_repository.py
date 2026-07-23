from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation_source import AutomationSource


class AutomationSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, source_id: int) -> AutomationSource | None:
        return self.db.get(AutomationSource, source_id)

    def get_active_for_automation(self, automation_id: int) -> AutomationSource | None:
        return self.db.scalar(
            select(AutomationSource)
            .where(AutomationSource.automation_id == automation_id, AutomationSource.is_active.is_(True))
            .order_by(AutomationSource.created_at.desc())
        )

    def find_github_source(
        self, integration_id: int, owner: str, repository: str, manifest_path: str
    ) -> AutomationSource | None:
        return self.db.scalar(
            select(AutomationSource).where(
                AutomationSource.type == "github",
                AutomationSource.integration_id == integration_id,
                AutomationSource.owner == owner,
                AutomationSource.repository == repository,
                AutomationSource.manifest_path == manifest_path,
            )
        )

    def list_for_integration(self, integration_id: int) -> list[AutomationSource]:
        return list(
            self.db.scalars(
                select(AutomationSource).where(AutomationSource.integration_id == integration_id)
            ).all()
        )

    def create(self, source: AutomationSource) -> AutomationSource:
        self.db.add(source)
        self.db.flush()
        return source

    def update(self, source: AutomationSource) -> AutomationSource:
        self.db.add(source)
        self.db.flush()
        return source
