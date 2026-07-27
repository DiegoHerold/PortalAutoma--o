from __future__ import annotations

from pathlib import Path

from app.integrations.storage.base import PackageStorage
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus


class PackageStorageObjectAdapter:
    provider_name = "package_storage"

    def __init__(self, storage: PackageStorage) -> None:
        self.storage = storage

    def put_file(self, bucket: str, object_key: str, file_path: Path, content_type: str) -> StoredObject:
        stored = self.storage.put(bucket, object_key, file_path, content_type)
        return StoredObject(
            id="",  # caller keeps the persisted identity
            bucket=stored.bucket,
            object_key=stored.object_key,
            content_type=stored.content_type,
            size_bytes=stored.size,
            sha256=None,
            etag=None,
            provider=self.provider_name,
            status=StoredObjectStatus.UPLOADED,
        )

    def object_exists(self, bucket: str, object_key: str) -> bool:
        return self.storage.exists(bucket, object_key)

    def open_local_path(self, bucket: str, object_key: str) -> Path:
        return self.storage.open_local_path(bucket, object_key)

    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str:
        return self.storage.get_download_url(bucket, object_key, expires_in_seconds)


class ApiTemporaryUrlProvider:
    def __init__(self, api_v1_prefix: str) -> None:
        self.api_v1_prefix = api_v1_prefix.rstrip("/")

    def create_upload_url(self, upload_session, expires_in_seconds: int = 900) -> str:
        return f"{self.api_v1_prefix}/package-uploads/{upload_session.id}/bytes"
