from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredObject:
    bucket: str
    object_key: str
    size: int
    content_type: str


class PackageStorage(ABC):
    """
    Storage abstraction for immutable automation package ZIPs. The DB only ever
    stores (bucket, object_key, size, sha256, content_type) — never the file
    bytes themselves (see docs/automation-package.md, section "Armazenamento").
    """

    @abstractmethod
    def put(self, bucket: str, object_key: str, file_path: Path, content_type: str = "application/zip") -> StoredObject: ...

    @abstractmethod
    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str:
        """A time-limited URL the Automation Agent can use to download the package."""
        ...

    @abstractmethod
    def exists(self, bucket: str, object_key: str) -> bool: ...

    @abstractmethod
    def delete(self, bucket: str, object_key: str) -> None: ...

    @abstractmethod
    def open_local_path(self, bucket: str, object_key: str) -> Path:
        """Returns a local filesystem path to read the object's bytes (for hashing/streaming)."""
        ...
