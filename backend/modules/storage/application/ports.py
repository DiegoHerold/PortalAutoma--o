from __future__ import annotations

from pathlib import Path
from typing import Protocol

from modules.storage.application.dto import ArtifactDTO, ArtifactUploadSessionLinkDTO
from modules.storage.domain.stored_object import StoredObject
from modules.storage.domain.upload_session import UploadSession


class ObjectStoragePort(Protocol):
    provider_name: str

    def put_file(self, bucket: str, object_key: str, file_path: Path, content_type: str) -> StoredObject:
        raise NotImplementedError

    def object_exists(self, bucket: str, object_key: str) -> bool:
        raise NotImplementedError

    def open_local_path(self, bucket: str, object_key: str) -> Path:
        raise NotImplementedError

    def get_download_url(self, bucket: str, object_key: str, expires_in_seconds: int = 300) -> str:
        raise NotImplementedError


class TemporaryUrlProvider(Protocol):
    def create_upload_url(self, upload_session: UploadSession, expires_in_seconds: int = 900) -> str | None:
        raise NotImplementedError


class StoredObjectRepository(Protocol):
    def add(self, stored_object: StoredObject) -> StoredObject:
        raise NotImplementedError

    def get(self, stored_object_id: str) -> StoredObject | None:
        raise NotImplementedError

    def update(self, stored_object: StoredObject) -> StoredObject:
        raise NotImplementedError


class UploadSessionRepository(Protocol):
    def add(self, upload_session: UploadSession) -> UploadSession:
        raise NotImplementedError

    def get(self, upload_session_id: str) -> UploadSession | None:
        raise NotImplementedError

    def update(self, upload_session: UploadSession) -> UploadSession:
        raise NotImplementedError


class ArtifactRepository(Protocol):
    def add(self, artifact: ArtifactDTO) -> ArtifactDTO:
        raise NotImplementedError

    def get(self, artifact_id: str) -> ArtifactDTO | None:
        raise NotImplementedError

    def get_by_upload_session(self, upload_session_id: str) -> ArtifactDTO | None:
        raise NotImplementedError

    def update(self, artifact: ArtifactDTO) -> ArtifactDTO:
        raise NotImplementedError

    def list_for_execution(self, execution_id: str) -> list[ArtifactDTO]:
        raise NotImplementedError

    def list(
        self,
        *,
        execution_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ArtifactDTO]:
        raise NotImplementedError

    def count_for_execution(self, execution_id: str) -> int:
        raise NotImplementedError


class ArtifactUploadSessionRepository(Protocol):
    def add(self, link: ArtifactUploadSessionLinkDTO) -> ArtifactUploadSessionLinkDTO:
        raise NotImplementedError

    def get_by_upload_session(self, upload_session_id: str) -> ArtifactUploadSessionLinkDTO | None:
        raise NotImplementedError


class ExecutionAttemptContextReader(Protocol):
    def get_context(self, execution_attempt_id: str):
        raise NotImplementedError


class StorageTransaction(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError
