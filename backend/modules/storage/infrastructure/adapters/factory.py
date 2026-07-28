from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.storage.factory import get_package_storage
from modules.storage.infrastructure.adapters.package_storage_adapter import (
    ApiArtifactTemporaryUrlProvider,
    PackageStorageObjectAdapter,
)
from modules.storage.infrastructure.repositories import (
    SqlAlchemyArtifactRepository,
    SqlAlchemyArtifactUploadSessionRepository,
    SqlAlchemyStoredObjectRepository,
    SqlAlchemyStorageTransaction,
    SqlAlchemyUploadSessionRepository,
)
from modules.telemetry.infrastructure.repositories import SqlAlchemyExecutionAttemptTelemetryReader


@dataclass(frozen=True)
class StorageAdapters:
    artifacts: SqlAlchemyArtifactRepository
    artifact_uploads: SqlAlchemyArtifactUploadSessionRepository
    stored_objects: SqlAlchemyStoredObjectRepository
    upload_sessions: SqlAlchemyUploadSessionRepository
    attempts: SqlAlchemyExecutionAttemptTelemetryReader
    object_storage: PackageStorageObjectAdapter
    temporary_urls: ApiArtifactTemporaryUrlProvider
    transaction: SqlAlchemyStorageTransaction


def build_storage_adapters(db: Session) -> StorageAdapters:
    settings = get_settings()
    return StorageAdapters(
        artifacts=SqlAlchemyArtifactRepository(db),
        artifact_uploads=SqlAlchemyArtifactUploadSessionRepository(db),
        stored_objects=SqlAlchemyStoredObjectRepository(db),
        upload_sessions=SqlAlchemyUploadSessionRepository(db),
        attempts=SqlAlchemyExecutionAttemptTelemetryReader(db),
        object_storage=PackageStorageObjectAdapter(get_package_storage()),
        temporary_urls=ApiArtifactTemporaryUrlProvider(settings.backend_public_url, settings.api_v1_prefix),
        transaction=SqlAlchemyStorageTransaction(db),
    )
