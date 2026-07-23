from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    automation_id: int
    cron_expression: str
    timezone: str
    is_active: bool = True


class ScheduleUpdate(ScheduleCreate):
    pass


class ScheduleRead(ScheduleCreate):
    id: int

    class Config:
        from_attributes = True
