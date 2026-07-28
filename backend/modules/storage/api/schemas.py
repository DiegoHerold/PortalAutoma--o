from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InitiateArtifactUploadRequest(BaseModel):
    execution_attempt_id: str
    name: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifact_id: str | None = None


class CompleteArtifactUploadRequest(BaseModel):
    execution_attempt_id: str | None = None
    upload_session_id: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None


class FailArtifactUploadRequest(BaseModel):
    execution_attempt_id: str | None = None
    upload_session_id: str | None = None
    reason: str = Field(min_length=1)
