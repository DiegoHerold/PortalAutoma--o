from datetime import datetime

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    automation_id: int
    priority: str = "normal"
    payload_json: dict = Field(default_factory=dict)
    scheduled_for: datetime | None = None


class JobRead(BaseModel):
    id: int
    automation_id: int
    requested_by_user_id: int | None
    status: str
    priority: str
    payload_json: dict | None
    scheduled_for: datetime | None
    assigned_worker_id: int | None
    error_message: str | None

    class Config:
        from_attributes = True
