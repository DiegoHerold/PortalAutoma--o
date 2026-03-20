from pydantic import BaseModel


class AutomationCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    category_id: int
    executor_type: str
    default_priority: str = "normal"
    timeout_seconds: int = 300
    max_retries: int = 0
    is_active: bool = True


class AutomationUpdate(AutomationCreate):
    pass


class AutomationRead(AutomationCreate):
    id: int

    class Config:
        from_attributes = True
