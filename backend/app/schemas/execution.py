from datetime import datetime

from pydantic import BaseModel


class ExecutionLogRead(BaseModel):
    id: int
    level: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionRead(BaseModel):
    id: int
    job_id: int
    worker_id: int | None
    execution_status: str
    started_at: datetime | None
    finished_at: datetime | None
    result_summary: str | None
    result_payload_json: dict | None
    logs: list[ExecutionLogRead] = []

    class Config:
        from_attributes = True
