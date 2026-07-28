from __future__ import annotations


class StorageError(ValueError):
    """Base error for execution artifact storage failures."""


class ArtifactNotFound(StorageError):
    """Raised when an Artifact cannot be found."""


class ArtifactValidationError(StorageError):
    """Raised when size or hash verification fails."""


class ArtifactSecurityError(StorageError):
    """Raised when an Agent or user cannot access an Artifact."""
