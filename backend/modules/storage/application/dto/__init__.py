from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactDTO:
    id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    name: str
    content_type: str
    status: str
    stored_object_id: str | None
    upload_session_id: str | None
    size_bytes: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    uploaded_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class ArtifactUploadSessionLinkDTO:
    id: str
    artifact_id: str
    upload_session_id: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class InitiateArtifactUploadCommand:
    execution_attempt_id: str
    name: str
    content_type: str
    size_bytes: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] | None = None
    artifact_id: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class CompleteArtifactUploadCommand:
    artifact_id: str
    execution_attempt_id: str | None = None
    upload_session_id: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None


@dataclass(frozen=True)
class FailArtifactUploadCommand:
    artifact_id: str
    reason: str
    execution_attempt_id: str | None = None
    upload_session_id: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None


@dataclass(frozen=True)
class StoreUploadedArtifactBytesCommand:
    upload_session_id: str
    file_path: Path
    content_type: str | None = None


@dataclass(frozen=True)
class ArtifactUploadInstructionsDTO:
    artifact: ArtifactDTO
    upload_url: str
    upload_session_id: str
    expires_at: datetime | None


def to_payload(value: Any) -> Any:
    if is_dataclass(value):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
