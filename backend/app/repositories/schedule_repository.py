from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Schedule


class ScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Schedule]:
        return list(self.db.scalars(select(Schedule).order_by(Schedule.created_at.desc())).all())

    def get(self, schedule_id: int) -> Schedule | None:
        return self.db.get(Schedule, schedule_id)

    def create(self, schedule: Schedule) -> Schedule:
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update(self, schedule: Schedule) -> Schedule:
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete(self, schedule: Schedule) -> None:
        self.db.delete(schedule)
        self.db.commit()
