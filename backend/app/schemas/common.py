from datetime import datetime

from pydantic import BaseModel


class TimestampedSchema(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
