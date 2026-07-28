from datetime import datetime

from pydantic import BaseModel


class WorkerCreate(BaseModel):
    name: str
    hostname: str
    ip_address: str | None = None
    agent_id: str | None = None
    machine_id: str | None = None
    agent_version: str | None = None
    os: str | None = None
    architecture: str | None = None
    capabilities_json: list | None = None
    last_payload_json: dict | None = None
    status: str = "offline"
    connectivity_status: str | None = None
    administrative_status: str | None = None
    health_status: str | None = None
    occupancy_status: str | None = None
    desired_version: str | None = None
    cpu_percentage: float | None = None
    memory_percentage: float | None = None
    disk_free_mb: int | None = None
    interactive_session: dict | None = None
    pools: dict | None = None
    alerts: list[str] | None = None
    max_concurrency: int = 1
    is_active: bool = True


class WorkerUpdate(WorkerCreate):
    pass


class WorkerRead(WorkerCreate):
    id: int
    last_heartbeat_at: datetime | None = None
    active_jobs: int = 0

    class Config:
        from_attributes = True
