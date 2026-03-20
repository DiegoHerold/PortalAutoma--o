from sqlalchemy.orm import Session

from app.repositories.schedule_repository import ScheduleRepository


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self.schedules = ScheduleRepository(db)

    def list_schedules(self):
        return self.schedules.list_all()
