from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation import Automation


class AutomationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Automation]:
        return list(self.db.scalars(select(Automation).order_by(Automation.name)).all())

    def get(self, automation_id: int) -> Automation | None:
        return self.db.get(Automation, automation_id)

    def get_by_slug(self, slug: str) -> Automation | None:
        return self.db.scalar(select(Automation).where(Automation.slug == slug))

    def get_by_key(self, key: str) -> Automation | None:
        return self.db.scalar(select(Automation).where(Automation.key == key))

    def create(self, automation: Automation) -> Automation:
        self.db.add(automation)
        self.db.commit()
        self.db.refresh(automation)
        return automation

    def update(self, automation: Automation) -> Automation:
        self.db.add(automation)
        self.db.commit()
        self.db.refresh(automation)
        return automation

    def delete(self, automation: Automation) -> None:
        self.db.delete(automation)
        self.db.commit()
