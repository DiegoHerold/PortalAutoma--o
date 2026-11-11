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
    @abstractmethod
    def put(self, bucket: str, object_key: str, file_path: Path, content_type: str = "application/zip") -> StoredObject: ...

    @abstractmethod
    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str: ...

    @abstractmethod
    def exists(self, bucket: str, object_key: str) -> bool: ...

    @abstractmethod
    def delete(self, bucket: str, object_key: str) -> None: ...

    @abstractmethod
    def open_local_path(self, bucket: str, object_key: str) -> Path: ...

    def read_bytes(self, bucket: str, object_key: str) -> bytes:
        """Conteúdo do objeto (imagens dos passos, servidas pela API com permissão)."""
        return self.open_local_path(bucket, object_key).read_bytes()

