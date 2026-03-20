from pydantic import BaseModel


class ScheduleRead(BaseModel):
    id: int
    automation_id: int
    cron_expression: str
    timezone: str
    is_active: bool

    class Config:
        from_attributes = True
