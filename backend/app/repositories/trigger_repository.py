from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trigger import Trigger


class TriggerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Trigger]:
        return list(self.db.scalars(select(Trigger).order_by(Trigger.created_at.desc())).all())

    def get(self, trigger_id: int) -> Trigger | None:
        return self.db.get(Trigger, trigger_id)

    def get_by_route_path(self, route_path: str) -> Trigger | None:
        return self.db.scalar(select(Trigger).where(Trigger.route_path == route_path))

    def create(self, trigger: Trigger) -> Trigger:
        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)
        return trigger
