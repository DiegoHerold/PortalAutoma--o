from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StoredObjectStatus(StrEnum):
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    INVALID = "invalid"
    DELETED = "deleted"


@dataclass(frozen=True)
class StoredObject:
    id: str
    bucket: str
    object_key: str
    content_type: str
    size_bytes: int | None
    sha256: str | None
    etag: str | None
    provider: str
    status: StoredObjectStatus
    created_at: datetime | None = None
    verified_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.bucket or not self.object_key:
            raise ValueError("StoredObject requires bucket and object_key.")
        if self.object_key.startswith("/") or ".." in self.object_key.split("/"):
            raise ValueError("StoredObject object_key must be a safe relative key.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("StoredObject size cannot be negative.")
