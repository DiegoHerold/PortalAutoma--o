from datetime import datetime

from pydantic import BaseModel


class WorkerRead(BaseModel):
    id: int
    name: str
    hostname: str
    ip_address: str | None = None
    status: str
    max_concurrency: int
    last_heartbeat_at: datetime | None = None
    is_active: bool

    class Config:
        from_attributes = True
