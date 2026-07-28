from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.catalog.application.dto import (
    AutomationDTO,
    AutomationSourceDTO,
    AutomationVersionDTO,
    CategoryDTO,
    PackageDTO,
    RuntimeDTO,
    RuntimeVersionDTO,
)
from modules.catalog.domain.manifest import AutomationManifest, ValidationResult
from modules.catalog.infrastructure.orm.models import (
    CatalogAutomationRecord as Automation,
    CatalogAutomationSourceRecord as AutomationSource,
    CatalogAutomationVersionRecord as AutomationVersion,
    AutomationManifestRecord,
    AutomationPackageRecord,
    RuntimeRecord,
    RuntimeVersionRecord,
)


class SqlAlchemyTransactionManager:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyCatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_categories(self) -> list[CategoryDTO]:
        rows = self.db.scalars(select(CatalogCategoryRecord).order_by(CatalogCategoryRecord.name)).all()
        return [self._category_to_dto(row) for row in rows]

    def get_category(self, category_id: int) -> CategoryDTO | None:
        row = self.db.get(CatalogCategoryRecord, category_id)
        return self._category_to_dto(row) if row else None

    def get_category_by_slug(self, slug: str) -> CategoryDTO | None:
        row = self.db.scalar(select(CatalogCategoryRecord).where(CatalogCategoryRecord.slug == str(slug).strip().lower()))
        return self._category_to_dto(row) if row else None

    def create_category(self, payload: dict[str, Any]) -> CategoryDTO:
        row = CatalogCategoryRecord(
            name=str(payload["name"]).strip(),
            slug=str(payload["slug"]).strip().lower(),
            description=payload.get("description"),
            is_active=bool(payload.get("is_active", True)),
        )
        self.db.add(row)
        self.db.flush()
        return self._category_to_dto(row)

    def update_category(self, category_id: int, payload: dict[str, Any]) -> CategoryDTO:
        row = self.db.get(CatalogCategoryRecord, category_id)
        if row is None:
            raise ValueError("Category not found.")
        for field in ["name", "slug", "description", "is_active"]:
            if field in payload:
                value = payload[field]
                setattr(row, field, str(value).strip().lower() if field == "slug" else value)
        self.db.add(row)
        self.db.flush()
        return self._category_to_dto(row)

    def archive_category(self, category_id: int) -> CategoryDTO:
        row = self.db.get(CatalogCategoryRecord, category_id)
        if row is None:
            raise ValueError("Category not found.")
        row.is_active = False
        self.db.add(row)
        self.db.flush()
        return self._category_to_dto(row)

    def list_automations(self) -> list[AutomationDTO]:
        rows = self.db.scalars(select(Automation).order_by(Automation.name)).all()
        return [self._automation_to_dto(row) for row in rows]

    def get_automation(self, automation_id: int) -> AutomationDTO | None:
        row = self.db.get(Automation, automation_id)
        return self._automation_to_dto(row) if row else None

    def get_automation_by_key(self, key: str) -> AutomationDTO | None:
        row = self.db.scalar(select(Automation).where(Automation.key == key))
        return self._automation_to_dto(row) if row else None

    def get_automation_by_slug(self, slug: str) -> AutomationDTO | None:
        row = self.db.scalar(select(Automation).where(Automation.slug == slug))
        return self._automation_to_dto(row) if row else None

    def create_automation(self, payload: dict[str, Any]) -> AutomationDTO:
        row = Automation(
            name=payload["name"],
            slug=payload["slug"],
            key=payload.get("key"),
            description=payload.get("description"),
            category_id=payload["category_id"],
            executor_type=payload["executor_type"],
            package_url=payload.get("package_url"),
            package_sha256=payload.get("package_sha256"),
            default_priority=payload.get("default_priority", "normal"),
            timeout_seconds=payload.get("timeout_seconds", 300),
            max_retries=payload.get("max_retries", 0),
            is_active=payload.get("is_active", True),
            status=payload.get("status", "active"),
            tags_json=payload.get("tags") or [],
            created_by_user_id=_int_or_none(payload.get("created_by")),
        )
        self.db.add(row)
        self.db.flush()
        return self._automation_to_dto(row)

    def update_automation(self, automation_id: int, payload: dict[str, Any]) -> AutomationDTO:
        row = self.db.get(Automation, automation_id)
        if row is None:
            raise ValueError("Automation not found.")
        for field in [
            "name",
            "slug",
            "description",
            "category_id",
            "executor_type",
            "package_url",
            "package_sha256",
            "default_priority",
            "timeout_seconds",
            "max_retries",
            "is_active",
        ]:
            if field in payload:
                setattr(row, field, payload[field])
        if "status" in payload:
            row.status = payload["status"]
        elif "is_active" in payload:
            row.status = "active" if payload["is_active"] else "disabled"
        if "tags" in payload:
            row.tags_json = payload["tags"]
        self.db.add(row)
        self.db.flush()
        return self._automation_to_dto(row)

    def archive_automation(self, automation_id: int) -> AutomationDTO:
        row = self.db.get(Automation, automation_id)
        if row is None:
            raise ValueError("Automation not found.")
        row.status = "archived"
        row.is_active = False
        self.db.add(row)
        self.db.flush()
        return self._automation_to_dto(row)

    def create_source(self, automation_id: int, payload: dict[str, Any]) -> AutomationSourceDTO:
        row = AutomationSource(automation_id=automation_id, **payload)
        self.db.add(row)
        self.db.flush()
        return self._source_to_dto(row)

    def list_sources(self, automation_id: int) -> list[AutomationSourceDTO]:
        rows = self.db.scalars(
            select(AutomationSource)
            .where(AutomationSource.automation_id == automation_id)
            .order_by(AutomationSource.created_at.desc())
        ).all()
        return [self._source_to_dto(row) for row in rows]

    def get_active_source(self, automation_id: int) -> AutomationSourceDTO | None:
        row = self.db.scalar(
            select(AutomationSource)
            .where(AutomationSource.automation_id == automation_id, AutomationSource.is_active.is_(True))
            .order_by(AutomationSource.created_at.desc())
        )
        return self._source_to_dto(row) if row else None

    def update_source(self, source_id: int, payload: dict[str, Any]) -> AutomationSourceDTO:
        row = self.db.get(AutomationSource, source_id)
        if row is None:
            raise ValueError("Automation source not found.")
        for key, value in payload.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return self._source_to_dto(row)

    def list_versions(self, automation_id: int) -> list[AutomationVersionDTO]:
        rows = self.db.scalars(
            select(AutomationVersion)
            .where(AutomationVersion.automation_id == automation_id)
            .order_by(AutomationVersion.created_at.desc())
        ).all()
        return [self._version_to_dto(row) for row in rows]

    def get_version(self, version_id: int) -> AutomationVersionDTO | None:
        row = self.db.get(AutomationVersion, version_id)
        return self._version_to_dto(row) if row else None

    def get_version_for_automation(self, automation_id: int, version_id: int) -> AutomationVersionDTO | None:
        row = self.db.scalar(
            select(AutomationVersion).where(
                AutomationVersion.id == version_id,
                AutomationVersion.automation_id == automation_id,
            )
        )
        return self._version_to_dto(row) if row else None

    def get_version_by_number(self, automation_id: int, version: str) -> AutomationVersionDTO | None:
        row = self.db.scalar(
            select(AutomationVersion).where(
                AutomationVersion.automation_id == automation_id,
                AutomationVersion.version == version,
            )
        )
        return self._version_to_dto(row) if row else None

    def get_latest_published_version(self, automation_id: int) -> AutomationVersionDTO | None:
        row = self.db.scalar(
            select(AutomationVersion)
            .where(AutomationVersion.automation_id == automation_id, AutomationVersion.status == "published")
            .order_by(AutomationVersion.published_at.desc())
        )
        return self._version_to_dto(row) if row else None

    def create_version(self, payload: dict[str, Any]) -> AutomationVersionDTO:
        row = AutomationVersion(
            automation_id=payload["automation_id"],
            source_id=payload.get("source_id"),
            version=payload["version"],
            manifest=payload.get("manifest") or {},
            manifest_schema_version=_schema_version_as_int(payload.get("manifest_schema_version")),
            runtime_id=payload["runtime_id"],
            runtime_version=payload.get("runtime_version"),
            entrypoint_type=payload["entrypoint_type"],
            entrypoint=payload.get("entrypoint") or {},
            application_type=payload.get("application_type", "source"),
            application_path=payload.get("application_path"),
            artifact_bucket=payload.get("artifact_bucket") or "pending",
            artifact_object_key=payload.get("artifact_object_key") or "pending",
            artifact_size=payload.get("artifact_size") or 0,
            artifact_sha256=payload.get("artifact_sha256") or ("0" * 64),
            source_commit_sha=payload.get("source_commit_sha"),
            source_path=payload.get("source_path"),
            release_notes=payload.get("release_notes"),
            source_repository=payload.get("source_repository"),
            source_branch=payload.get("source_branch"),
            source_tag=payload.get("source_tag"),
            build_id=payload.get("build_id"),
            created_by=payload.get("created_by"),
            status=payload.get("status", "draft"),
            validation_errors=payload.get("validation_errors"),
        )
        self.db.add(row)
        self.db.flush()
        return self._version_to_dto(row)

    def update_version(self, version_id: int, payload: dict[str, Any]) -> AutomationVersionDTO:
        row = self.db.get(AutomationVersion, version_id)
        if row is None:
            raise ValueError("Automation version not found.")
        for key, value in payload.items():
            if key == "status":
                row.status = value
                now = datetime.utcnow()
                if value == "published":
                    row.published_at = row.published_at or now
                if value == "deprecated":
                    row.deprecated_at = row.deprecated_at or now
                if value == "blocked":
                    row.blocked_at = row.blocked_at or now
                continue
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return self._version_to_dto(row)

    def create_manifest(self, automation_version_id: int, raw_content: str, manifest: AutomationManifest, validation: ValidationResult) -> str:
        record = AutomationManifestRecord(
            id=str(uuid4()),
            automation_version_id=automation_version_id,
            schema_version=manifest.schema_version,
            raw_content=raw_content,
            normalized_content=manifest.normalized,
            content_hash=manifest.content_hash,
            validation_status="valid" if validation.is_valid else "invalid",
            validation_errors=validation.to_payload() or None,
            validator_version="catalog-v1",
            validated_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.flush()
        return record.id

    def get_manifest(self, manifest_id: str) -> dict[str, Any] | None:
        row = self.db.get(AutomationManifestRecord, manifest_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "automation_version_id": row.automation_version_id,
            "schema_version": row.schema_version,
            "raw_content": row.raw_content,
            "normalized_content": row.normalized_content,
            "content_hash": row.content_hash,
            "validation_status": row.validation_status,
            "validation_errors": row.validation_errors,
        }

    def create_package(self, payload: dict[str, Any]) -> PackageDTO:
        row = AutomationPackageRecord(id=str(uuid4()), **payload)
        self.db.add(row)
        self.db.flush()
        return self._package_to_dto(row)

    def get_package(self, package_id: str) -> PackageDTO | None:
        row = self.db.get(AutomationPackageRecord, package_id)
        return self._package_to_dto(row) if row else None

    def get_package_by_stored_object(self, stored_object_id: str) -> PackageDTO | None:
        row = self.db.scalar(
            select(AutomationPackageRecord).where(AutomationPackageRecord.stored_object_id == stored_object_id)
        )
        return self._package_to_dto(row) if row else None

    def update_package(self, package_id: str, payload: dict[str, Any]) -> PackageDTO:
        row = self.db.get(AutomationPackageRecord, package_id)
        if row is None:
            raise ValueError("Automation package not found.")
        for key, value in payload.items():
            setattr(row, key, value)
        if payload.get("status") in {"valid", "invalid"}:
            row.validated_at = row.validated_at or datetime.utcnow()
        if payload.get("status") == "published":
            row.published_at = row.published_at or datetime.utcnow()
        if payload.get("status") == "blocked":
            row.blocked_at = row.blocked_at or datetime.utcnow()
        self.db.add(row)
        self.db.flush()
        return self._package_to_dto(row)

    def list_runtimes(self) -> list[RuntimeDTO]:
        rows = self.db.scalars(select(RuntimeRecord).order_by(RuntimeRecord.name)).all()
        return [self._runtime_to_dto(row) for row in rows]

    def get_runtime(self, runtime_id: str) -> RuntimeDTO | None:
        row = self.db.get(RuntimeRecord, runtime_id)
        return self._runtime_to_dto(row) if row else None

    def get_runtime_by_key(self, key: str) -> RuntimeDTO | None:
        row = self.db.scalar(select(RuntimeRecord).where(RuntimeRecord.key == key))
        return self._runtime_to_dto(row) if row else None

    def create_runtime(self, payload: dict[str, Any]) -> RuntimeDTO:
        row = RuntimeRecord(
            id=payload.get("id") or str(uuid4()),
            key=payload["key"],
            name=payload["name"],
            description=payload.get("description"),
            status=payload.get("status", "active"),
        )
        self.db.add(row)
        self.db.flush()
        return self._runtime_to_dto(row)

    def create_runtime_version(self, payload: dict[str, Any]) -> RuntimeVersionDTO:
        row = RuntimeVersionRecord(
            id=payload.get("id") or str(uuid4()),
            runtime_id=payload["runtime_id"],
            version=payload["version"],
            operating_system=payload["operating_system"],
            architecture=payload["architecture"],
            status=payload.get("status", "draft"),
            minimum_agent_version=payload.get("minimum_agent_version"),
            supported_entrypoints=payload.get("supported_entrypoints") or [],
            supported_execution_modes=payload.get("supported_execution_modes") or [],
            metadata_json=payload.get("metadata") or {},
        )
        self.db.add(row)
        self.db.flush()
        return self._runtime_version_to_dto(row)

    def get_runtime_version(self, runtime_version_id: str) -> RuntimeVersionDTO | None:
        row = self.db.get(RuntimeVersionRecord, runtime_version_id)
        return self._runtime_version_to_dto(row) if row else None

    def find_runtime_version(self, runtime_key: str, version: str | None) -> RuntimeVersionDTO | None:
        query = (
            select(RuntimeVersionRecord)
            .join(RuntimeRecord, RuntimeRecord.id == RuntimeVersionRecord.runtime_id)
            .where(RuntimeRecord.key == runtime_key, RuntimeVersionRecord.status == "published")
        )
        if version:
            query = query.where(RuntimeVersionRecord.version == version)
        row = self.db.scalar(query.order_by(RuntimeVersionRecord.published_at.desc()))
        return self._runtime_version_to_dto(row) if row else None

    def update_runtime_version(self, runtime_version_id: str, payload: dict[str, Any]) -> RuntimeVersionDTO:
        row = self.db.get(RuntimeVersionRecord, runtime_version_id)
        if row is None:
            raise ValueError("RuntimeVersion not found.")
        for key, value in payload.items():
            if key == "metadata":
                row.metadata_json = value
            elif key == "status":
                row.status = value
                now = datetime.utcnow()
                if value == "published":
                    row.published_at = row.published_at or now
                if value == "deprecated":
                    row.deprecated_at = row.deprecated_at or now
                if value == "blocked":
                    row.blocked_at = row.blocked_at or now
            else:
                setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return self._runtime_version_to_dto(row)

    def _automation_to_dto(self, row: Automation) -> AutomationDTO:
        return AutomationDTO(
            id=row.id,
            key=row.key,
            name=row.name,
            slug=row.slug,
            description=row.description,
            category_id=row.category_id,
            executor_type=row.executor_type,
            package_url=row.package_url,
            package_sha256=row.package_sha256,
            default_priority=row.default_priority,
            timeout_seconds=row.timeout_seconds,
            max_retries=row.max_retries,
            is_active=row.is_active,
            status=getattr(row, "status", "active" if row.is_active else "disabled"),
            tags=list(getattr(row, "tags_json", None) or []),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _category_to_dto(self, row: CatalogCategoryRecord) -> CategoryDTO:
        return CategoryDTO(
            id=row.id,
            name=row.name,
            slug=row.slug,
            description=row.description,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _source_to_dto(self, row: AutomationSource) -> AutomationSourceDTO:
        return AutomationSourceDTO(
            id=row.id,
            automation_id=row.automation_id,
            type=row.type,
            integration_id=row.integration_id,
            owner=row.owner,
            repository=row.repository,
            branch=row.branch,
            automation_path=row.automation_path,
            manifest_path=row.manifest_path,
            last_commit_sha=row.last_commit_sha,
            last_synced_at=row.last_synced_at,
            sync_status=row.sync_status,
            original_filename=row.original_filename,
            uploaded_at=row.uploaded_at,
        )

    def _version_to_dto(self, row: AutomationVersion) -> AutomationVersionDTO:
        return AutomationVersionDTO(
            id=row.id,
            automation_id=row.automation_id,
            version=row.version,
            status=row.status,
            runtime_id=row.runtime_id,
            runtime_version=row.runtime_version,
            entrypoint_type=row.entrypoint_type,
            application_type=row.application_type,
            artifact_bucket=row.artifact_bucket,
            artifact_object_key=row.artifact_object_key,
            artifact_size=row.artifact_size,
            artifact_sha256=row.artifact_sha256,
            source_commit_sha=row.source_commit_sha,
            source_path=row.source_path,
            created_at=row.created_at,
            published_at=row.published_at,
            manifest_id=getattr(row, "manifest_id", None),
            package_id=getattr(row, "package_id", None),
            runtime_version_id=getattr(row, "runtime_version_id", None),
            validation_errors=row.validation_errors,
        )

    def _package_to_dto(self, row: AutomationPackageRecord) -> PackageDTO:
        return PackageDTO(
            id=row.id,
            automation_version_id=row.automation_version_id,
            stored_object_id=row.stored_object_id,
            package_format=row.package_format,
            file_name=row.file_name,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            status=row.status,
            validation_result=row.validation_result,
        )

    def _runtime_to_dto(self, row: RuntimeRecord) -> RuntimeDTO:
        return RuntimeDTO(
            id=row.id,
            key=row.key,
            name=row.name,
            description=row.description,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _runtime_version_to_dto(self, row: RuntimeVersionRecord) -> RuntimeVersionDTO:
        return RuntimeVersionDTO(
            id=row.id,
            runtime_id=row.runtime_id,
            version=row.version,
            operating_system=row.operating_system,
            architecture=row.architecture,
            status=row.status,
            minimum_agent_version=row.minimum_agent_version,
            supported_entrypoints=list(row.supported_entrypoints or []),
            supported_execution_modes=list(row.supported_execution_modes or []),
            metadata=dict(row.metadata_json or {}),
            created_at=row.created_at,
            published_at=row.published_at,
            deprecated_at=row.deprecated_at,
            blocked_at=row.blocked_at,
        )


def _schema_version_as_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 1


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
