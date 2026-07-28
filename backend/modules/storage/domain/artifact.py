from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from modules.storage.domain.states import ArtifactStatus


@dataclass(frozen=True)
class Artifact:
    id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    name: str
    content_type: str
    status: ArtifactStatus
    stored_object_id: str | None
    upload_session_id: str | None
    size_bytes: int | None = None
    sha256: str | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None
    uploaded_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.execution_id or not self.task_execution_id or not self.execution_attempt_id:
            raise ValueError("Artifact requires execution, task and attempt identifiers.")
        if not self.name:
            raise ValueError("Artifact requires a name.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("Artifact size cannot be negative.")
