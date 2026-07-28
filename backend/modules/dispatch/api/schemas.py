from __future__ import annotations

from pydantic import BaseModel, Field


class RetryTaskRequest(BaseModel):
    reason: str = "manual_retry"
    source_attempt_id: str | None = None
    error_code: str | None = None


class QueueResponse(BaseModel):
    items: list[dict] = Field(default_factory=list)

