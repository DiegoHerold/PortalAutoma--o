from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from modules.storage.application.dto import (
    ArtifactDTO,
    ArtifactUploadInstructionsDTO,
    ArtifactUploadSessionLinkDTO,
    CompleteArtifactUploadCommand,
    FailArtifactUploadCommand,
    InitiateArtifactUploadCommand,
    StoreUploadedArtifactBytesCommand,
)
from modules.storage.application.ports import (
    ArtifactRepository,
    ArtifactUploadSessionRepository,
    ExecutionAttemptContextReader,
    ObjectStoragePort,
    StoredObjectRepository,
    StorageTransaction,
    TemporaryUrlProvider,
    UploadSessionRepository,
)
from modules.storage.domain.errors import ArtifactNotFound, ArtifactSecurityError, ArtifactValidationError
from modules.storage.domain.states import ArtifactStatus
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus


ARTIFACT_BUCKET = "execution-artifacts"


class InitiateArtifactUpload:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        artifact_uploads: ArtifactUploadSessionRepository,
        stored_objects: StoredObjectRepository,
        upload_sessions: UploadSessionRepository,
        attempts: ExecutionAttemptContextReader,
        object_storage: ObjectStoragePort,
        temporary_urls: TemporaryUrlProvider,
        transaction: StorageTransaction,
    ) -> None:
        self.artifacts = artifacts
        self.artifact_uploads = artifact_uploads
        self.stored_objects = stored_objects
        self.upload_sessions = upload_sessions
        self.attempts = attempts
        self.object_storage = object_storage
        self.temporary_urls = temporary_urls
        self.transaction = transaction

    def execute(self, command: InitiateArtifactUploadCommand) -> ArtifactUploadInstructionsDTO:
        try:
            context = _require_context(self.attempts, command.execution_attempt_id)
            _ensure_agent(context, command.agent_id, command.agent_instance_id)
            if command.artifact_id:
                existing = self.artifacts.get(command.artifact_id)
                if existing is not None:
                    if existing.execution_attempt_id != command.execution_attempt_id:
                        raise ArtifactSecurityError("Artifact belongs to another ExecutionAttempt.")
                    upload_session = _require_upload_session(self.upload_sessions, existing.upload_session_id)
                    self.transaction.commit()
                    return ArtifactUploadInstructionsDTO(
                        artifact=existing,
                        upload_url=upload_session.upload_url or "",
                        upload_session_id=upload_session.id,
                        expires_at=upload_session.expires_at,
                    )
            now = utcnow()
            artifact_id = command.artifact_id or new_id("art")
            stored_object_id = str(uuid4())
            object_key = _object_key(context.execution_id, context.execution_attempt_id, artifact_id, command.name)
            stored_object = self.stored_objects.add(
                StoredObject(
                    id=stored_object_id,
                    bucket=ARTIFACT_BUCKET,
                    object_key=object_key,
                    content_type=command.content_type or "application/octet-stream",
                    size_bytes=None,
                    sha256=None,
                    etag=None,
                    provider=self.object_storage.provider_name,
                    status=StoredObjectStatus.PENDING,
                    created_at=now,
                )
            )
            upload_session = UploadSession(
                id=str(uuid4()),
                stored_object_id=stored_object.id,
                upload_url=None,
                status=UploadSessionStatus.INITIATED,
                expected_size_bytes=command.size_bytes,
                expected_sha256=command.sha256,
                created_by=command.created_by or command.agent_id,
                created_at=now,
                expires_at=now + timedelta(minutes=15),
            )
            upload_url = self.temporary_urls.create_upload_url(upload_session)
            upload_session = self.upload_sessions.add(replace(upload_session, upload_url=upload_url))
            artifact = self.artifacts.add(
                ArtifactDTO(
                    id=artifact_id,
                    execution_id=context.execution_id,
                    task_execution_id=context.task_execution_id,
                    execution_attempt_id=context.execution_attempt_id,
                    name=command.name,
                    content_type=command.content_type or "application/octet-stream",
                    status=ArtifactStatus.CREATED.value,
                    stored_object_id=stored_object.id,
                    upload_session_id=upload_session.id,
                    size_bytes=command.size_bytes,
                    sha256=command.sha256,
                    metadata=command.metadata or {},
                    created_at=now,
                )
            )
            self.artifact_uploads.add(
                ArtifactUploadSessionLinkDTO(
                    id=new_id("aus"),
                    artifact_id=artifact.id,
                    upload_session_id=upload_session.id,
                    created_at=now,
                )
            )
            self.transaction.commit()
            return ArtifactUploadInstructionsDTO(
                artifact=artifact,
                upload_url=upload_url,
                upload_session_id=upload_session.id,
                expires_at=upload_session.expires_at,
            )
        except Exception:
            self.transaction.rollback()
            raise


class StoreUploadedArtifactBytes:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        stored_objects: StoredObjectRepository,
        upload_sessions: UploadSessionRepository,
        object_storage: ObjectStoragePort,
        transaction: StorageTransaction,
    ) -> None:
        self.artifacts = artifacts
        self.stored_objects = stored_objects
        self.upload_sessions = upload_sessions
        self.object_storage = object_storage
        self.transaction = transaction

    def execute(self, command: StoreUploadedArtifactBytesCommand) -> ArtifactDTO:
        try:
            upload_session = _require_upload_session(self.upload_sessions, command.upload_session_id)
            if upload_session.expires_at and _naive(upload_session.expires_at) < utcnow():
                self.upload_sessions.update(replace(upload_session, status=UploadSessionStatus.EXPIRED))
                self.transaction.commit()
                raise ArtifactValidationError("UploadSession expired.")
            artifact = self.artifacts.get_by_upload_session(upload_session.id)
            if artifact is None:
                raise ArtifactNotFound("Artifact not found for upload session.")
            stored_object = _require_stored_object(self.stored_objects, upload_session.stored_object_id)
            sha256, size_bytes = _hash_file(command.file_path)
            uploaded = self.object_storage.put_file(
                stored_object.bucket,
                stored_object.object_key,
                command.file_path,
                command.content_type or stored_object.content_type,
            )
            self.stored_objects.update(
                replace(
                    stored_object,
                    content_type=command.content_type or stored_object.content_type,
                    size_bytes=uploaded.size_bytes,
                    sha256=sha256,
                    etag=uploaded.etag,
                    status=StoredObjectStatus.UPLOADED,
                )
            )
            self.upload_sessions.update(replace(upload_session, status=UploadSessionStatus.UPLOADING))
            saved = self.artifacts.update(
                replace(
                    artifact,
                    status=ArtifactStatus.UPLOADING.value,
                    size_bytes=size_bytes,
                    sha256=sha256,
                )
            )
            self.transaction.commit()
            return saved
        except Exception:
            self.transaction.rollback()
            raise


class CompleteArtifactUpload:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        stored_objects: StoredObjectRepository,
        upload_sessions: UploadSessionRepository,
        attempts: ExecutionAttemptContextReader,
        object_storage: ObjectStoragePort,
        transaction: StorageTransaction,
    ) -> None:
        self.artifacts = artifacts
        self.stored_objects = stored_objects
        self.upload_sessions = upload_sessions
        self.attempts = attempts
        self.object_storage = object_storage
        self.transaction = transaction

    def execute(self, command: CompleteArtifactUploadCommand) -> ArtifactDTO:
        try:
            artifact = _require_artifact(self.artifacts, command.artifact_id)
            if artifact.status == ArtifactStatus.AVAILABLE.value:
                self.transaction.commit()
                return artifact
            if command.execution_attempt_id and artifact.execution_attempt_id != command.execution_attempt_id:
                raise ArtifactSecurityError("Artifact belongs to another ExecutionAttempt.")
            context = _require_context(self.attempts, artifact.execution_attempt_id)
            _ensure_agent(context, command.agent_id, command.agent_instance_id)
            upload_session = _require_upload_session(self.upload_sessions, command.upload_session_id or artifact.upload_session_id)
            stored_object = _require_stored_object(self.stored_objects, artifact.stored_object_id)
            if not self.object_storage.object_exists(stored_object.bucket, stored_object.object_key):
                raise ArtifactValidationError("Uploaded artifact bytes were not found.")
            local_path = self.object_storage.open_local_path(stored_object.bucket, stored_object.object_key)
            actual_sha256, actual_size = _hash_file(local_path)
            expected_size = command.size_bytes if command.size_bytes is not None else upload_session.expected_size_bytes
            expected_sha256 = command.sha256 or upload_session.expected_sha256
            if expected_size is not None and expected_size != actual_size:
                return self._fail_verification(artifact, stored_object, upload_session, f"Artifact size mismatch: expected {expected_size}, got {actual_size}.")
            if expected_sha256 and expected_sha256.lower() != actual_sha256:
                return self._fail_verification(artifact, stored_object, upload_session, "Artifact sha256 mismatch.")
            now = utcnow()
            self.stored_objects.update(
                replace(stored_object, size_bytes=actual_size, sha256=actual_sha256, status=StoredObjectStatus.VERIFIED, verified_at=now)
            )
            self.upload_sessions.update(replace(upload_session, status=UploadSessionStatus.COMPLETED, completed_at=now))
            saved = self.artifacts.update(
                replace(
                    artifact,
                    status=ArtifactStatus.AVAILABLE.value,
                    size_bytes=actual_size,
                    sha256=actual_sha256,
                    uploaded_at=now,
                    failure_reason=None,
                    failed_at=None,
                )
            )
            self.transaction.commit()
            return saved
        except Exception:
            self.transaction.rollback()
            raise

    def _fail_verification(self, artifact: ArtifactDTO, stored_object: StoredObject, upload_session: UploadSession, reason: str) -> ArtifactDTO:
        now = utcnow()
        self.stored_objects.update(replace(stored_object, status=StoredObjectStatus.INVALID))
        self.upload_sessions.update(replace(upload_session, status=UploadSessionStatus.FAILED, aborted_at=now))
        failed = self.artifacts.update(
            replace(
                artifact,
                status=ArtifactStatus.FAILED.value,
                failed_at=now,
                failure_reason=reason,
            )
        )
        self.transaction.commit()
        raise ArtifactValidationError(reason)


class FailArtifactUpload:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        upload_sessions: UploadSessionRepository,
        attempts: ExecutionAttemptContextReader,
        transaction: StorageTransaction,
    ) -> None:
        self.artifacts = artifacts
        self.upload_sessions = upload_sessions
        self.attempts = attempts
        self.transaction = transaction

    def execute(self, command: FailArtifactUploadCommand) -> ArtifactDTO:
        try:
            artifact = _require_artifact(self.artifacts, command.artifact_id)
            if command.execution_attempt_id and artifact.execution_attempt_id != command.execution_attempt_id:
                raise ArtifactSecurityError("Artifact belongs to another ExecutionAttempt.")
            context = _require_context(self.attempts, artifact.execution_attempt_id)
            _ensure_agent(context, command.agent_id, command.agent_instance_id)
            now = utcnow()
            upload_session = self.upload_sessions.get(command.upload_session_id or artifact.upload_session_id or "")
            if upload_session is not None:
                self.upload_sessions.update(replace(upload_session, status=UploadSessionStatus.FAILED, aborted_at=now))
            saved = self.artifacts.update(
                replace(
                    artifact,
                    status=ArtifactStatus.FAILED.value,
                    failed_at=now,
                    failure_reason=command.reason,
                )
            )
            self.transaction.commit()
            return saved
        except Exception:
            self.transaction.rollback()
            raise


class GetArtifact:
    def __init__(self, artifacts: ArtifactRepository) -> None:
        self.artifacts = artifacts

    def execute(self, artifact_id: str) -> ArtifactDTO:
        return _require_artifact(self.artifacts, artifact_id)


class ListExecutionArtifacts:
    def __init__(self, artifacts: ArtifactRepository) -> None:
        self.artifacts = artifacts

    def execute(self, execution_id: str) -> list[ArtifactDTO]:
        return self.artifacts.list_for_execution(execution_id)


def _require_context(attempts: ExecutionAttemptContextReader, execution_attempt_id: str):
    context = attempts.get_context(execution_attempt_id)
    if context is None:
        raise ArtifactNotFound("ExecutionAttempt not found.")
    return context


def _ensure_agent(context, agent_id: str | None, agent_instance_id: str | None) -> None:
    if agent_id is not None and context.agent_id != agent_id:
        raise ArtifactSecurityError("Artifact message belongs to another Agent.")
    if agent_instance_id is not None and context.agent_instance_id != agent_instance_id:
        raise ArtifactSecurityError("Artifact message belongs to another AgentInstance.")


def _require_artifact(artifacts: ArtifactRepository, artifact_id: str) -> ArtifactDTO:
    artifact = artifacts.get(artifact_id)
    if artifact is None:
        raise ArtifactNotFound("Artifact not found.")
    return artifact


def _require_upload_session(upload_sessions: UploadSessionRepository, upload_session_id: str | None) -> UploadSession:
    if not upload_session_id:
        raise ArtifactNotFound("UploadSession not found.")
    upload_session = upload_sessions.get(upload_session_id)
    if upload_session is None:
        raise ArtifactNotFound("UploadSession not found.")
    return upload_session


def _require_stored_object(stored_objects: StoredObjectRepository, stored_object_id: str | None) -> StoredObject:
    if not stored_object_id:
        raise ArtifactNotFound("StoredObject not found.")
    stored_object = stored_objects.get(stored_object_id)
    if stored_object is None:
        raise ArtifactNotFound("StoredObject not found.")
    return stored_object


def _object_key(execution_id: str, attempt_id: str, artifact_id: str, name: str) -> str:
    return f"{execution_id}/{attempt_id}/{artifact_id}/{_safe_filename(name)}"


def _safe_filename(name: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return candidate or "artifact.bin"


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.utcnow()


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value
