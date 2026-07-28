from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.security import create_package_download_token
from app.integrations.storage.base import PackageStorage, StoredObject


class LocalPackageStorage(PackageStorage):
    """
    Filesystem-backed storage under `local_storage_path` (mount a Docker volume
    there in production). Used when no MinIO/S3 is configured. Download URLs
    point at the backend's own signed-download endpoint
    (`GET /api/automations/artifacts/download`).
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(self.settings.local_storage_path)

    def _path_for(self, bucket: str, object_key: str) -> Path:
        return self.root / bucket / object_key

    def put(self, bucket: str, object_key: str, file_path: Path, content_type: str = "application/zip") -> StoredObject:
        target = self._path_for(bucket, object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file_path, target)
        return StoredObject(bucket=bucket, object_key=object_key, size=target.stat().st_size, content_type=content_type)

    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str:
        token = create_package_download_token(bucket, object_key, expires_in_seconds)
        base = self.settings.backend_public_url.rstrip("/")
        return f"{base}{self.settings.api_v1_prefix}/automations/artifacts/download?token={token}"

    def exists(self, bucket: str, object_key: str) -> bool:
        return self._path_for(bucket, object_key).is_file()

    def delete(self, bucket: str, object_key: str) -> None:
        path = self._path_for(bucket, object_key)
        if path.is_file():
            path.unlink()

    def open_local_path(self, bucket: str, object_key: str) -> Path:
        return self._path_for(bucket, object_key)
