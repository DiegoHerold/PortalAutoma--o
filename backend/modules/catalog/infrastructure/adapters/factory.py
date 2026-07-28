from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.storage import get_package_storage
from modules.catalog.infrastructure.package_validation import ZipPackageValidator
from modules.catalog.infrastructure.repositories import SqlAlchemyCatalogRepository, SqlAlchemyTransactionManager
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.storage.infrastructure.adapters import ApiTemporaryUrlProvider, PackageStorageObjectAdapter
from modules.storage.infrastructure.repositories import (
    SqlAlchemyStoredObjectRepository,
    SqlAlchemyUploadSessionRepository,
)
from modules.telemetry.infrastructure.repositories import SqlAlchemyOutboxRepository


@dataclass
class CatalogModuleAdapters:
    catalog: SqlAlchemyCatalogRepository
    audit: SqlAlchemyAuditEventRepository
    outbox: SqlAlchemyOutboxRepository
    transaction: SqlAlchemyTransactionManager
    stored_objects: SqlAlchemyStoredObjectRepository
    upload_sessions: SqlAlchemyUploadSessionRepository
    object_storage: PackageStorageObjectAdapter
    temporary_urls: ApiTemporaryUrlProvider
    package_validator: ZipPackageValidator
    packages_bucket_name: str
    max_package_size_bytes: int


def build_catalog_adapters(db: Session) -> CatalogModuleAdapters:
    settings = get_settings()
    return CatalogModuleAdapters(
        catalog=SqlAlchemyCatalogRepository(db),
        audit=SqlAlchemyAuditEventRepository(db),
        outbox=SqlAlchemyOutboxRepository(db),
        transaction=SqlAlchemyTransactionManager(db),
        stored_objects=SqlAlchemyStoredObjectRepository(db),
        upload_sessions=SqlAlchemyUploadSessionRepository(db),
        object_storage=PackageStorageObjectAdapter(get_package_storage()),
        temporary_urls=ApiTemporaryUrlProvider(settings.api_v1_prefix),
        package_validator=ZipPackageValidator(),
        packages_bucket_name=settings.packages_bucket_name,
        max_package_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
