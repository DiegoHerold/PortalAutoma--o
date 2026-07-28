from __future__ import annotations

import tempfile
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import get_settings
from app.integrations.storage.base import PackageStorage, StoredObject


class S3PackageStorage(PackageStorage):
    """S3-compatible storage (AWS S3 or MinIO) via boto3."""

    def __init__(self) -> None:
        self.settings = get_settings()
        boto_config = BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path" if self.settings.s3_use_path_style else "auto"},
        )
        # Internal client: put/head/delete, talks to MinIO over the Docker
        # network using the service name (fast, doesn't need to be publicly
        # reachable).
        self._client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url or None,
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.s3_access_key or None,
            aws_secret_access_key=self.settings.s3_secret_key or None,
            config=boto_config,
        )
        # Public client: only used to mint presigned download URLs, which get
        # handed to the Automation Agent on a different machine. Must point at
        # an address that machine can actually resolve/reach — see
        # s3_public_endpoint_url in app.core.config for why this is separate
        # from the internal client above.
        public_endpoint = self.settings.s3_public_endpoint_url or self.settings.s3_endpoint_url
        self._public_client = boto3.client(
            "s3",
            endpoint_url=public_endpoint or None,
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.s3_access_key or None,
            aws_secret_access_key=self.settings.s3_secret_key or None,
            config=boto_config,
        )

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
        except Exception:
            self._client.create_bucket(Bucket=bucket)

    def put(self, bucket: str, object_key: str, file_path: Path, content_type: str = "application/zip") -> StoredObject:
        self._ensure_bucket(bucket)
        self._client.upload_file(
            str(file_path), bucket, object_key, ExtraArgs={"ContentType": content_type}
        )
        size = file_path.stat().st_size
        return StoredObject(bucket=bucket, object_key=object_key, size=size, content_type=content_type)

    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str:
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in_seconds,
        )

    def exists(self, bucket: str, object_key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=object_key)
            return True
        except Exception:
            return False

    def delete(self, bucket: str, object_key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=object_key)

    def open_local_path(self, bucket: str, object_key: str) -> Path:
        """Downloads to a temp file and returns its path (used for hashing/re-reads)."""
        tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
        self._client.download_file(bucket, object_key, str(tmp))
        return tmp
