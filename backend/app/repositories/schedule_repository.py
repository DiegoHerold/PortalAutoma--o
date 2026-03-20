from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Schedule


class ScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Schedule]:
        return list(self.db.scalars(select(Schedule).order_by(Schedule.created_at.desc())).all())
