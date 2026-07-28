from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UploadSessionStatus(StrEnum):
    INITIATED = "initiated"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    ABORTED = "aborted"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class UploadSession:
    id: str
    stored_object_id: str
    upload_url: str | None
    status: UploadSessionStatus
    expected_size_bytes: int | None = None
    expected_sha256: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    aborted_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.expected_size_bytes is not None and self.expected_size_bytes < 0:
            raise ValueError("UploadSession expected_size_bytes cannot be negative.")
