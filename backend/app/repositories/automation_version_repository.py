from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation_version import AutomationVersion


class AutomationVersionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, version_id: int) -> AutomationVersion | None:
        return self.db.get(AutomationVersion, version_id)

    def get_by_version(self, automation_id: int, version: str) -> AutomationVersion | None:
        return self.db.scalar(
            select(AutomationVersion).where(
                AutomationVersion.automation_id == automation_id,
                AutomationVersion.version == version,
            )
        )

    def list_for_automation(self, automation_id: int) -> list[AutomationVersion]:
        return list(
            self.db.scalars(
                select(AutomationVersion)
                .where(AutomationVersion.automation_id == automation_id)
                .order_by(AutomationVersion.created_at.desc())
            ).all()
        )

    def get_latest_published(self, automation_id: int) -> AutomationVersion | None:
        return self.db.scalar(
            select(AutomationVersion)
            .where(AutomationVersion.automation_id == automation_id, AutomationVersion.status == "published")
            .order_by(AutomationVersion.published_at.desc())
        )

    def create(self, version: AutomationVersion) -> AutomationVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def update(self, version: AutomationVersion) -> AutomationVersion:
        self.db.add(version)
        self.db.flush()
        return version
