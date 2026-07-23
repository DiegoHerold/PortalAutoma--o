from pydantic import BaseModel


class WorkerPreferenceItem(BaseModel):
    worker_id: int
    priority_order: int


class WorkerPreferenceUpdate(BaseModel):
    preferences: list[WorkerPreferenceItem]


class WorkerPreferenceResponse(BaseModel):
    worker_id: int
    worker_name: str
    priority_order: int
    is_active: bool

    model_config = {"from_attributes": True}
