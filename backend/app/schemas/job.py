from datetime import datetime

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    automation_id: int
    priority: str | None = None
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
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime | None
    
    # Extended fields for frontend
    automation_name: str | None = None
    worker_name: str | None = None
    estimated_start: datetime | None = None
    estimated_end: datetime | None = None
    estimated_duration_seconds: int | None = None
    queue_position: int | None = None

    class Config:
        from_attributes = True

