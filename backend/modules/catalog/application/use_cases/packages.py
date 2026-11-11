from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, PackageDTO, PackageUploadDTO
from modules.catalog.application.ports import (
    AuditRecorder,
    CatalogRepository,
    ObjectStoragePort,
    OutboxPort,
    PackageValidatorPort,
    StoredObjectRepository,
    TemporaryUrlProvider,
    TransactionManager,
    UploadSessionRepository,
)
from modules.catalog.domain.errors import CatalogValidationError, PackageValidationError
from modules.catalog.domain.events import CatalogEvent
from modules.governance.domain.audit import AuditEvent
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus


@dataclass
class InitiatePackageUpload:
    catalog: CatalogRepository
    stored_objects: StoredObjectRepository
    upload_sessions: UploadSessionRepository
    temporary_urls: TemporaryUrlProvider
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager
    bucket_name: str

    def execute(
        self,
        automation_version_id: int,
        file_name: str,
        expected_size_bytes: int | None,
        expected_sha256: str | None,
        actor: ActorDTO,
    ) -> PackageUploadDTO:
        version = self.catalog.get_version(automation_version_id)
        if version is None:
            raise CatalogValidationError("Automation version not found.")
        if version.status in {"published", "deprecated", "blocked"}:
            raise CatalogValidationError("Cannot upload package for an immutable automation version.")

        stored_object = StoredObject(
            id=str(uuid4()),
            bucket=self.bucket_name,
            object_key=f"automation-packages/{automation_version_id}/{uuid4()}-{file_name}",
            content_type="application/zip",
            size_bytes=None,
            sha256=None,
            etag=None,
            provider="pending",
            status=StoredObjectStatus.PENDING,
        )
        stored_object = self.stored_objects.add(stored_object)
        upload_session = UploadSession(
            id=str(uuid4()),
            stored_object_id=stored_object.id,
            upload_url=None,
            status=UploadSessionStatus.INITIATED,
            expected_size_bytes=expected_size_bytes,
            expected_sha256=expected_sha256,
            created_by=actor.actor_id or actor.actor_email,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        upload_url = self.temporary_urls.create_upload_url(upload_session, expires_in_seconds=1800)
        upload_session = UploadSession(
            id=upload_session.id,
            stored_object_id=upload_session.stored_object_id,
            upload_url=upload_url,
            status=upload_session.status,
            expected_size_bytes=upload_session.expected_size_bytes,
            expected_sha256=upload_session.expected_sha256,
            created_by=upload_session.created_by,
            created_at=upload_session.created_at,
            expires_at=upload_session.expires_at,
        )
        upload_session = self.upload_sessions.add(upload_session)
        package = self.catalog.create_package(
            {
                "automation_version_id": automation_version_id,
                "stored_object_id": stored_object.id,
                "package_format": "zip",
                "file_name": file_name,
                "size_bytes": expected_size_bytes or 0,
                "sha256": expected_sha256 or ("0" * 64),
                "status": "uploading",
            }
        )
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="package.upload_initiated",
                resource_type="automation_package",
                resource_id=package.id,
                after={"automation_version_id": automation_version_id, "stored_object_id": stored_object.id},
            )
        )
        self.outbox.append_catalog_event(
            CatalogEvent("package.upload_initiated", "AutomationPackage", package.id, {"version_id": automation_version_id})
        )
        self.transaction.commit()
        return PackageUploadDTO(
            id=upload_session.id,
            stored_object_id=stored_object.id,
            package_id=package.id,
            upload_url=upload_url,
            expires_at=upload_session.expires_at,
        )


@dataclass
class CompletePackageUpload:
    catalog: CatalogRepository
    stored_objects: StoredObjectRepository
    upload_sessions: UploadSessionRepository
    object_storage: ObjectStoragePort
    package_validator: PackageValidatorPort
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager
    max_size_bytes: int

    def execute(self, upload_session_id: str, actor: ActorDTO, uploaded_file_path: Path | None = None) -> PackageDTO:
        upload_session = self.upload_sessions.get(upload_session_id)
        if upload_session is None:
            raise CatalogValidationError("Upload session not found.")
        if upload_session.status in {UploadSessionStatus.COMPLETED, UploadSessionStatus.ABORTED, UploadSessionStatus.EXPIRED}:
            raise CatalogValidationError(f"Upload session is already {upload_session.status}.")
        stored_object = self.stored_objects.get(upload_session.stored_object_id)
        if stored_object is None:
            raise CatalogValidationError("Stored object not found.")
        if uploaded_file_path is not None:
            uploaded_object = self.object_storage.put_file(
                stored_object.bucket,
                stored_object.object_key,
                uploaded_file_path,
                stored_object.content_type,
            )
            stored_object = StoredObject(
                id=stored_object.id,
                bucket=uploaded_object.bucket,
                object_key=uploaded_object.object_key,
                content_type=uploaded_object.content_type,
                size_bytes=uploaded_object.size_bytes,
                sha256=uploaded_object.sha256,
                etag=uploaded_object.etag,
                provider=uploaded_object.provider,
                status=uploaded_object.status,
                created_at=stored_object.created_at,
                verified_at=stored_object.verified_at,
                deleted_at=stored_object.deleted_at,
            )
        elif not self.object_storage.object_exists(stored_object.bucket, stored_object.object_key):
            raise CatalogValidationError("Uploaded object was not found in storage.")

        local_path = self.object_storage.open_local_path(stored_object.bucket, stored_object.object_key)
        size_bytes = local_path.stat().st_size
        if upload_session.expected_size_bytes is not None and upload_session.expected_size_bytes != size_bytes:
            raise PackageValidationError("Uploaded object size does not match the expected size.")
        sha256 = _sha256_file(local_path)
        if upload_session.expected_sha256 is not None and upload_session.expected_sha256 != sha256:
            raise PackageValidationError("Uploaded object sha256 does not match the expected hash.")

        validation = self.package_validator.validate_zip_package(local_path, self.max_size_bytes)
        package = self._package_for_stored_object(stored_object.id)
        status = "valid" if validation.get("valid") else "invalid"
        updated_object = StoredObject(
            id=stored_object.id,
            bucket=stored_object.bucket,
            object_key=stored_object.object_key,
            content_type=stored_object.content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            etag=stored_object.etag,
            provider=self.object_storage.provider_name,
            status=StoredObjectStatus.VERIFIED if status == "valid" else StoredObjectStatus.INVALID,
            created_at=stored_object.created_at,
            verified_at=datetime.now(UTC),
        )
        self.stored_objects.update(updated_object)
        completed = UploadSession(
            id=upload_session.id,
            stored_object_id=upload_session.stored_object_id,
            upload_url=upload_session.upload_url,
            status=UploadSessionStatus.COMPLETED,
            expected_size_bytes=upload_session.expected_size_bytes,
            expected_sha256=upload_session.expected_sha256,
            created_by=upload_session.created_by,
            created_at=upload_session.created_at,
            expires_at=upload_session.expires_at,
            completed_at=datetime.now(UTC),
        )
        self.upload_sessions.update(completed)
        package = self.catalog.update_package(
            package.id,
            {
                "size_bytes": size_bytes,
                "sha256": sha256,
                "status": status,
                "validation_result": validation,
            },
        )
        version_status = "draft" if status == "valid" else "blocked"
        self.catalog.update_version(
            package.automation_version_id,
            {
                "package_id": package.id,
                "status": version_status,
                "artifact_bucket": stored_object.bucket,
                "artifact_object_key": stored_object.object_key,
                "artifact_size": size_bytes,
                "artifact_sha256": sha256,
            },
        )
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="package.upload_completed",
                resource_type="automation_package",
                resource_id=package.id,
                after={"status": status, "sha256": sha256},
            )
        )
        event_type = "package.validated" if status == "valid" else "package.validation_failed"
        self.outbox.append_catalog_event(CatalogEvent(event_type, "AutomationPackage", package.id, validation))
        self.transaction.commit()
        return package

    def _package_for_stored_object(self, stored_object_id: str) -> PackageDTO:
        package = self.catalog.get_package_by_stored_object(stored_object_id)
        if package is None:
            raise CatalogValidationError("Automation package not found for stored object.")
        return package


@dataclass
class AbortPackageUpload:
    upload_sessions: UploadSessionRepository
    audit: AuditRecorder
    transaction: TransactionManager

    def execute(self, upload_session_id: str, actor: ActorDTO) -> None:
        upload_session = self.upload_sessions.get(upload_session_id)
        if upload_session is None:
            raise CatalogValidationError("Upload session not found.")
        aborted = UploadSession(
            id=upload_session.id,
            stored_object_id=upload_session.stored_object_id,
            upload_url=upload_session.upload_url,
            status=UploadSessionStatus.ABORTED,
            expected_size_bytes=upload_session.expected_size_bytes,
            expected_sha256=upload_session.expected_sha256,
            created_by=upload_session.created_by,
            created_at=upload_session.created_at,
            expires_at=upload_session.expires_at,
            aborted_at=datetime.now(UTC),
        )
        self.upload_sessions.update(aborted)
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="package.upload_aborted",
                resource_type="upload_session",
                resource_id=upload_session_id,
            )
        )
        self.transaction.commit()


@dataclass
class GetPackage:
    catalog: CatalogRepository

    def execute(self, package_id: str) -> PackageDTO:
        package = self.catalog.get_package(package_id)
        if package is None:
            raise CatalogValidationError("Automation package not found.")
        return package


@dataclass
class GetPackageValidation:
    catalog: CatalogRepository

    def execute(self, package_id: str) -> dict:
        package = self.catalog.get_package(package_id)
        if package is None:
            raise CatalogValidationError("Automation package not found.")
        return package.validation_result or {"valid": False, "issues": []}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
