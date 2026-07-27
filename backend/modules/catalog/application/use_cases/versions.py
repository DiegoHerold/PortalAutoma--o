from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, AutomationVersionDTO
from modules.catalog.application.ports import AuditRecorder, CatalogRepository, OutboxPort, TransactionManager
from modules.catalog.domain.errors import (
    CatalogValidationError,
    DuplicateAutomationVersionError,
    ImmutablePublishedVersionError,
    RuntimeCompatibilityError,
)
from modules.catalog.domain.events import automation_version_event
from modules.catalog.domain.manifest import parse_automation_manifest
from modules.catalog.domain.states import AutomationPackageStatus, RuntimeVersionStatus
from modules.catalog.domain.value_objects import SemVer
from modules.governance.domain.audit import AuditEvent


@dataclass
class ListAutomationVersions:
    catalog: CatalogRepository

    def execute(self, automation_id: int) -> list[AutomationVersionDTO]:
        return self.catalog.list_versions(automation_id)


@dataclass
class GetAutomationVersion:
    catalog: CatalogRepository

    def execute(self, version_id: int) -> AutomationVersionDTO:
        version = self.catalog.get_version(version_id)
        if version is None:
            raise CatalogValidationError("Automation version not found.")
        return version


@dataclass
class CreateAutomationVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, payload: dict[str, Any], raw_manifest: str, actor: ActorDTO) -> AutomationVersionDTO:
        automation = self.catalog.get_automation(automation_id)
        if automation is None:
            raise CatalogValidationError("Automation not found.")
        manifest, validation = parse_automation_manifest(raw_manifest)
        if manifest is None:
            raise CatalogValidationError("Manifest is invalid.")
        if manifest.id != automation.key:
            raise CatalogValidationError("Manifest automation id does not match Automation key.")
        SemVer(manifest.version)
        if self.catalog.get_version_by_number(automation_id, manifest.version) is not None:
            raise DuplicateAutomationVersionError(f"Version already exists: {manifest.version}")
        version = self.catalog.create_version(
            {
                "automation_id": automation_id,
                "version": manifest.version,
                "manifest": manifest.raw,
                "manifest_schema_version": manifest.schema_version,
                "runtime_id": manifest.runtime_id,
                "runtime_version": manifest.runtime_version,
                "entrypoint_type": manifest.entrypoint_type,
                "entrypoint": manifest.entrypoint,
                "application_type": payload.get("application_type", "source"),
                "application_path": payload.get("application_path"),
                "artifact_bucket": payload.get("artifact_bucket", ""),
                "artifact_object_key": payload.get("artifact_object_key", ""),
                "artifact_size": payload.get("artifact_size", 0),
                "artifact_sha256": payload.get("artifact_sha256", ""),
                "source_commit_sha": payload.get("source_commit_sha"),
                "source_path": payload.get("source_path"),
                "status": payload.get("status", "draft"),
                "release_notes": payload.get("release_notes"),
                "source_repository": payload.get("source_repository"),
                "source_branch": payload.get("source_branch"),
                "source_tag": payload.get("source_tag"),
                "build_id": payload.get("build_id"),
                "created_by": actor.actor_id or actor.actor_email,
                "validation_errors": validation.to_payload() or None,
            }
        )
        manifest_id = self.catalog.create_manifest(version.id, raw_manifest, manifest, validation)
        version = self.catalog.update_version(version.id, {"manifest_id": manifest_id})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.created",
                resource_type="automation_version",
                resource_id=str(version.id),
                after={"automation_id": automation_id, "version": version.version},
            )
        )
        self.outbox.append_catalog_event(
            automation_version_event(
                "automation_version.created",
                str(version.id),
                {"automation_id": automation_id, "version": version.version},
            )
        )
        self.transaction.commit()
        return version


@dataclass
class ValidateAutomationVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, version_id: int, actor: ActorDTO) -> AutomationVersionDTO:
        version = self.catalog.get_version(version_id)
        if version is None:
            raise CatalogValidationError("Automation version not found.")
        manifest_record = self.catalog.get_manifest(version.manifest_id) if version.manifest_id else None
        if manifest_record is None:
            raise CatalogValidationError("Automation version has no persisted manifest.")
        status = "draft" if not manifest_record.get("validation_errors") else "blocked"
        updated = self.catalog.update_version(version_id, {"status": status, "validation_errors": manifest_record.get("validation_errors")})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.validation_started",
                resource_type="automation_version",
                resource_id=str(version_id),
                after={"status": updated.status},
            )
        )
        self.outbox.append_catalog_event(
            automation_version_event("automation_version.validated", str(version_id), {"status": updated.status})
        )
        self.transaction.commit()
        return updated


@dataclass
class PublishAutomationVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, version_id: int, actor: ActorDTO) -> AutomationVersionDTO:
        automation = self.catalog.get_automation(automation_id)
        version = self.catalog.get_version_for_automation(automation_id, version_id)
        if automation is None or version is None:
            raise CatalogValidationError("Automation version not found.")
        if automation.status == "archived" or automation.is_active is False:
            raise CatalogValidationError("Archived or disabled automations cannot publish new versions.")
        if version.status == "published":
            return version
        if version.status in {"deprecated", "blocked"}:
            raise ImmutablePublishedVersionError("Deprecated or blocked versions cannot be published.")
        if not version.manifest_id:
            raise CatalogValidationError("Version requires a valid manifest before publication.")
        if not version.package_id:
            raise CatalogValidationError("Version requires a valid package before publication.")
        package = self.catalog.get_package(version.package_id)
        if package is None or package.status not in {AutomationPackageStatus.VALID, AutomationPackageStatus.PUBLISHED, "valid", "published"}:
            raise CatalogValidationError("Version requires a valid package before publication.")
        runtime_version = self.catalog.find_runtime_version(version.runtime_id, version.runtime_version)
        if runtime_version is None and version.runtime_version_id:
            runtime_version = self.catalog.get_runtime_version(version.runtime_version_id)
        if runtime_version is None or runtime_version.status != RuntimeVersionStatus.PUBLISHED:
            raise RuntimeCompatibilityError("RuntimeVersion must exist and be published before publishing an AutomationVersion.")

        current = self.catalog.get_latest_published_version(automation_id)
        if current is not None and current.id != version.id:
            self.catalog.update_version(current.id, {"status": "deprecated"})
        updated = self.catalog.update_version(
            version_id,
            {
                "status": "published",
                "runtime_version_id": runtime_version.id,
                "published_by": actor.actor_id or actor.actor_email,
            },
        )
        self.catalog.update_package(package.id, {"status": "published"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.published",
                resource_type="automation_version",
                resource_id=str(version_id),
                after={"automation_id": automation_id, "version": updated.version},
            )
        )
        self.outbox.append_catalog_event(
            automation_version_event("automation_version.published", str(version_id), {"automation_id": automation_id})
        )
        self.transaction.commit()
        return updated


@dataclass
class DeprecateAutomationVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, version_id: int, actor: ActorDTO) -> AutomationVersionDTO:
        version = self.catalog.get_version_for_automation(automation_id, version_id)
        if version is None:
            raise CatalogValidationError("Automation version not found.")
        if version.status != "published":
            raise CatalogValidationError("Only published versions can be deprecated.")
        updated = self.catalog.update_version(version_id, {"status": "deprecated"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.deprecated",
                resource_type="automation_version",
                resource_id=str(version_id),
            )
        )
        self.outbox.append_catalog_event(automation_version_event("automation_version.deprecated", str(version_id), {}))
        self.transaction.commit()
        return updated


@dataclass
class BlockAutomationVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, version_id: int, actor: ActorDTO, reason: str | None = None) -> AutomationVersionDTO:
        version = self.catalog.get_version_for_automation(automation_id, version_id)
        if version is None:
            raise CatalogValidationError("Automation version not found.")
        updated = self.catalog.update_version(version_id, {"status": "blocked"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.blocked",
                resource_type="automation_version",
                resource_id=str(version_id),
                metadata={"reason": reason},
            )
        )
        self.outbox.append_catalog_event(automation_version_event("automation_version.blocked", str(version_id), {"reason": reason}))
        self.transaction.commit()
        return updated
