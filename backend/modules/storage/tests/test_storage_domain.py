from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from modules.storage.application.dto import ArtifactDTO, InitiateArtifactUploadCommand
from modules.storage.application.use_cases.artifacts import InitiateArtifactUpload
from modules.storage.domain.states import ArtifactStatus
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus


def test_stored_object_rejects_unsafe_object_key() -> None:
    try:
        StoredObject(
            id="1",
            bucket="packages",
            object_key="../package.zip",
            content_type="application/zip",
            size_bytes=10,
            sha256=None,
            etag=None,
            provider="local",
            status=StoredObjectStatus.PENDING,
        )
    except ValueError:
        return
    raise AssertionError("unsafe object_key should be rejected")


def test_initiate_artifact_upload_refreshes_expired_existing_session() -> None:
    now = datetime.utcnow()
    stored_object = StoredObject(
        id="obj-1",
        bucket="execution-artifacts",
        object_key="exec-1/att-1/art-1/report.txt",
        content_type="text/plain",
        size_bytes=None,
        sha256=None,
        etag=None,
        provider="test",
        status=StoredObjectStatus.PENDING,
    )
    artifact = ArtifactDTO(
        id="art-1",
        execution_id="exec-1",
        task_execution_id="task-1",
        execution_attempt_id="att-1",
        name="report.txt",
        content_type="text/plain",
        status=ArtifactStatus.CREATED.value,
        stored_object_id=stored_object.id,
        upload_session_id="upl-old",
        size_bytes=7,
        sha256="sha-old",
    )
    old_session = UploadSession(
        id="upl-old",
        stored_object_id=stored_object.id,
        upload_url="https://portal/upload/upl-old",
        status=UploadSessionStatus.INITIATED,
        expected_size_bytes=7,
        expected_sha256="sha-old",
        created_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=1),
    )
    artifacts = _ArtifactRepo({"art-1": artifact})
    sessions = _UploadSessionRepo({"upl-old": old_session})
    links = _ArtifactUploadLinkRepo()

    result = InitiateArtifactUpload(
        artifacts,
        links,
        _StoredObjectRepo({stored_object.id: stored_object}),
        sessions,
        _AttemptContextReader(),
        _ObjectStorage(),
        _TemporaryUrls(),
        _Transaction(),
    ).execute(
        InitiateArtifactUploadCommand(
            execution_attempt_id="att-1",
            artifact_id="art-1",
            name="report.txt",
            content_type="text/plain",
            size_bytes=7,
            sha256="sha-old",
            agent_id="agt-1",
            agent_instance_id="agi-1",
        )
    )

    assert result.upload_session_id != "upl-old"
    assert result.upload_url.endswith(f"/{result.upload_session_id}")
    assert artifacts.items["art-1"].upload_session_id == result.upload_session_id
    assert sessions.items[result.upload_session_id].expires_at > now
    assert links.items[-1].artifact_id == "art-1"
    assert links.items[-1].upload_session_id == result.upload_session_id


@dataclass
class _AttemptContext:
    execution_id: str = "exec-1"
    task_execution_id: str = "task-1"
    execution_attempt_id: str = "att-1"
    agent_id: str = "agt-1"
    agent_instance_id: str = "agi-1"


class _AttemptContextReader:
    def get_context(self, execution_attempt_id: str):
        return _AttemptContext() if execution_attempt_id == "att-1" else None


class _ArtifactRepo:
    def __init__(self, items: dict[str, ArtifactDTO]) -> None:
        self.items = items

    def add(self, artifact: ArtifactDTO) -> ArtifactDTO:
        self.items[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> ArtifactDTO | None:
        return self.items.get(artifact_id)

    def get_by_upload_session(self, upload_session_id: str) -> ArtifactDTO | None:
        return next((item for item in self.items.values() if item.upload_session_id == upload_session_id), None)

    def update(self, artifact: ArtifactDTO) -> ArtifactDTO:
        self.items[artifact.id] = artifact
        return artifact


class _StoredObjectRepo:
    def __init__(self, items: dict[str, StoredObject]) -> None:
        self.items = items

    def add(self, stored_object: StoredObject) -> StoredObject:
        self.items[stored_object.id] = stored_object
        return stored_object

    def get(self, stored_object_id: str) -> StoredObject | None:
        return self.items.get(stored_object_id)

    def update(self, stored_object: StoredObject) -> StoredObject:
        self.items[stored_object.id] = stored_object
        return stored_object


class _UploadSessionRepo:
    def __init__(self, items: dict[str, UploadSession]) -> None:
        self.items = items

    def add(self, upload_session: UploadSession) -> UploadSession:
        self.items[upload_session.id] = upload_session
        return upload_session

    def get(self, upload_session_id: str) -> UploadSession | None:
        return self.items.get(upload_session_id)

    def update(self, upload_session: UploadSession) -> UploadSession:
        self.items[upload_session.id] = upload_session
        return upload_session


class _ArtifactUploadLinkRepo:
    def __init__(self) -> None:
        self.items = []

    def add(self, link):
        self.items.append(link)
        return link

    def get_by_upload_session(self, upload_session_id: str):
        return next((item for item in self.items if item.upload_session_id == upload_session_id), None)


class _ObjectStorage:
    provider_name = "test"


class _TemporaryUrls:
    def create_upload_url(self, upload_session: UploadSession, expires_in_seconds: int = 900) -> str:
        return f"https://portal/upload/{upload_session.id}"


class _Transaction:
    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
