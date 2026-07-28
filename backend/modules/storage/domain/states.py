from __future__ import annotations

from enum import StrEnum


class ArtifactStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    AVAILABLE = "available"
    FAILED = "failed"
    EXPIRED = "expired"
    DELETED = "deleted"
