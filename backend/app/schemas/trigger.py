from pydantic import BaseModel


class TriggerCreate(BaseModel):
    automation_id: int
    trigger_type: str = "https"
    route_path: str
    secret_token: str
    is_active: bool = True


class TriggerRead(TriggerCreate):
    id: int

    class Config:
        from_attributes = True
