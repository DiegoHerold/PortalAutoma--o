from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from modules.catalog.application.dto import (
    AutomationDTO,
    AutomationSourceDTO,
    AutomationVersionDTO,
    PackageDTO,
    RuntimeDTO,
    RuntimeVersionDTO,
)
from modules.catalog.domain.events import CatalogEvent
from modules.catalog.domain.manifest import AutomationManifest, ValidationResult
from modules.governance.domain.audit import AuditEvent
from modules.storage.domain.stored_object import StoredObject
from modules.storage.domain.upload_session import UploadSession


class TransactionManager(Protocol):
    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class CatalogRepository(Protocol):
    def list_automations(self) -> list[AutomationDTO]:
        raise NotImplementedError

    def get_automation(self, automation_id: int) -> AutomationDTO | None:
        raise NotImplementedError

    def get_automation_by_key(self, key: str) -> AutomationDTO | None:
        raise NotImplementedError

    def get_automation_by_slug(self, slug: str) -> AutomationDTO | None:
        raise NotImplementedError

    def create_automation(self, payload: dict[str, Any]) -> AutomationDTO:
        raise NotImplementedError

    def update_automation(self, automation_id: int, payload: dict[str, Any]) -> AutomationDTO:
        raise NotImplementedError

    def archive_automation(self, automation_id: int) -> AutomationDTO:
        raise NotImplementedError

    def create_source(self, automation_id: int, payload: dict[str, Any]) -> AutomationSourceDTO:
        raise NotImplementedError

    def list_sources(self, automation_id: int) -> list[AutomationSourceDTO]:
        raise NotImplementedError

    def get_active_source(self, automation_id: int) -> AutomationSourceDTO | None:
        raise NotImplementedError

    def update_source(self, source_id: int, payload: dict[str, Any]) -> AutomationSourceDTO:
        raise NotImplementedError

    def list_versions(self, automation_id: int) -> list[AutomationVersionDTO]:
        raise NotImplementedError

    def get_version(self, version_id: int) -> AutomationVersionDTO | None:
        raise NotImplementedError

    def get_version_for_automation(self, automation_id: int, version_id: int) -> AutomationVersionDTO | None:
        raise NotImplementedError

    def get_version_by_number(self, automation_id: int, version: str) -> AutomationVersionDTO | None:
        raise NotImplementedError

    def get_latest_published_version(self, automation_id: int) -> AutomationVersionDTO | None:
        raise NotImplementedError

    def create_version(self, payload: dict[str, Any]) -> AutomationVersionDTO:
        raise NotImplementedError

    def update_version(self, version_id: int, payload: dict[str, Any]) -> AutomationVersionDTO:
        raise NotImplementedError

    def create_manifest(self, automation_version_id: int, raw_content: str, manifest: AutomationManifest, validation: ValidationResult) -> str:
        raise NotImplementedError

    def get_manifest(self, manifest_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def create_package(self, payload: dict[str, Any]) -> PackageDTO:
        raise NotImplementedError

    def get_package(self, package_id: str) -> PackageDTO | None:
        raise NotImplementedError

    def get_package_by_stored_object(self, stored_object_id: str) -> PackageDTO | None:
        raise NotImplementedError

    def update_package(self, package_id: str, payload: dict[str, Any]) -> PackageDTO:
        raise NotImplementedError

    def list_runtimes(self) -> list[RuntimeDTO]:
        raise NotImplementedError

    def get_runtime(self, runtime_id: str) -> RuntimeDTO | None:
        raise NotImplementedError

    def get_runtime_by_key(self, key: str) -> RuntimeDTO | None:
        raise NotImplementedError

    def create_runtime(self, payload: dict[str, Any]) -> RuntimeDTO:
        raise NotImplementedError

    def create_runtime_version(self, payload: dict[str, Any]) -> RuntimeVersionDTO:
        raise NotImplementedError

    def get_runtime_version(self, runtime_version_id: str) -> RuntimeVersionDTO | None:
        raise NotImplementedError

    def find_runtime_version(self, runtime_key: str, version: str | None) -> RuntimeVersionDTO | None:
        raise NotImplementedError

    def update_runtime_version(self, runtime_version_id: str, payload: dict[str, Any]) -> RuntimeVersionDTO:
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


class PackageValidatorPort(Protocol):
    def validate_zip_package(self, file_path: Path, max_size_bytes: int) -> dict[str, Any]:
        raise NotImplementedError


class OutboxPort(Protocol):
    def append_catalog_event(self, event: CatalogEvent) -> None:
        raise NotImplementedError


class AuditRecorder(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent:
        raise NotImplementedError
