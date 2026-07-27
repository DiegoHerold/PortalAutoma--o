from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, AutomationVersionDTO
from modules.catalog.application.ports import (
    AuditRecorder,
    CatalogRepository,
    OutboxPort,
    StoredObjectRepository,
    TransactionManager,
)
from modules.catalog.domain.errors import CatalogValidationError, DuplicateAutomationVersionError
from modules.catalog.domain.events import CatalogEvent
from modules.catalog.domain.manifest import parse_automation_manifest
from modules.governance.domain.audit import AuditEvent
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus


@dataclass
class ConfirmStagedAutomationImport:
    catalog: CatalogRepository
    stored_objects: StoredObjectRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, staged: dict, actor: ActorDTO, category_id: int | None) -> AutomationVersionDTO:
        raw_manifest_yaml = staged.get("raw_manifest_yaml") or json.dumps(staged["manifest"]["raw"], ensure_ascii=False)
        manifest, validation = parse_automation_manifest(raw_manifest_yaml)
        if manifest is None:
            raise CatalogValidationError("Manifest is invalid.")
        automation = self.catalog.get_automation_by_key(manifest.id)
        if automation is None:
            if category_id is None:
                raise CatalogValidationError("category_id is required for new automations.")
            automation = self.catalog.create_automation(
                {
                    "name": manifest.name,
                    "slug": _slugify(manifest.name),
                    "key": manifest.id,
                    "description": manifest.description,
                    "category_id": category_id,
                    "executor_type": "python_script",
                    "package_url": None,
                    "package_sha256": None,
                    "default_priority": "normal",
                    "timeout_seconds": manifest.execution.timeout_seconds,
                    "max_retries": 0,
                    "is_active": True,
                    "status": "active",
                    "created_by": actor.actor_id,
                }
            )
            self.audit.append(
                AuditEvent(
                    id=str(uuid4()),
                    actor_type=actor.actor_type,
                    actor_id=actor.actor_id or actor.actor_email,
                    action="automation.created",
                    resource_type="automation",
                    resource_id=str(automation.id),
                    after={"key": manifest.id, "source": staged["source_type"]},
                )
            )
        if self.catalog.get_version_by_number(automation.id, manifest.version) is not None:
            raise DuplicateAutomationVersionError(f"Version already exists: {manifest.version}")

        source = self.catalog.create_source(automation.id, _source_payload(staged, actor))
        package_payload = staged["package"]
        stored_object = self.stored_objects.add(
            StoredObject(
                id=str(uuid4()),
                bucket=package_payload["bucket"],
                object_key=package_payload["object_key"],
                content_type="application/zip",
                size_bytes=package_payload["size"],
                sha256=package_payload["sha256"],
                etag=None,
                provider="legacy_package_storage",
                status=StoredObjectStatus.VERIFIED,
            )
        )
        first_version = self.catalog.get_latest_published_version(automation.id) is None
        runtime_version = self.catalog.find_runtime_version(manifest.runtime_id, manifest.runtime_version)
        version = self.catalog.create_version(
            {
                "automation_id": automation.id,
                "source_id": source.id,
                "version": manifest.version,
                "manifest": manifest.raw,
                "manifest_schema_version": manifest.schema_version,
                "runtime_id": manifest.runtime_id,
                "runtime_version": manifest.runtime_version,
                "runtime_version_id": runtime_version.id if runtime_version else None,
                "entrypoint_type": manifest.entrypoint_type,
                "entrypoint": manifest.entrypoint,
                "application_type": package_payload.get("application_type", "source"),
                "application_path": package_payload.get("application_path"),
                "artifact_bucket": package_payload["bucket"],
                "artifact_object_key": package_payload["object_key"],
                "artifact_size": package_payload["size"],
                "artifact_sha256": package_payload["sha256"],
                "source_commit_sha": staged.get("commit_sha"),
                "source_path": staged.get("automation_path"),
                "source_repository": _source_repository(staged),
                "source_branch": staged.get("github", {}).get("branch"),
                "status": "published" if first_version and runtime_version else "ready",
                "created_by": actor.actor_id or actor.actor_email,
                "published_by": actor.actor_id or actor.actor_email if first_version and runtime_version else None,
                "validation_errors": validation.to_payload() or None,
            }
        )
        manifest_id = self.catalog.create_manifest(version.id, raw_manifest_yaml, manifest, validation)
        package = self.catalog.create_package(
            {
                "automation_version_id": version.id,
                "stored_object_id": stored_object.id,
                "package_format": "zip",
                "file_name": PurePosixPath(package_payload["object_key"]).name,
                "size_bytes": package_payload["size"],
                "sha256": package_payload["sha256"],
                "status": "published" if version.status == "published" else "valid",
                "validation_result": {"valid": True, "issues": []},
            }
        )
        version = self.catalog.update_version(
            version.id,
            {
                "manifest_id": manifest_id,
                "package_id": package.id,
                "runtime_version_id": runtime_version.id if runtime_version else None,
            },
        )
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation_version.created",
                resource_type="automation_version",
                resource_id=str(version.id),
                after={
                    "automation_id": automation.id,
                    "version": version.version,
                    "source_type": staged["source_type"],
                    "status": version.status,
                },
            )
        )
        if version.status == "published":
            self.audit.append(
                AuditEvent(
                    id=str(uuid4()),
                    actor_type=actor.actor_type,
                    actor_id=actor.actor_id or actor.actor_email,
                    action="automation_version.published",
                    resource_type="automation_version",
                    resource_id=str(version.id),
                )
            )
        self.outbox.append_catalog_event(
            CatalogEvent(
                "automation_version.imported",
                "AutomationVersion",
                str(version.id),
                {"automation_id": automation.id, "version": version.version, "status": version.status},
            )
        )
        self.transaction.commit()
        return version


def _source_payload(staged: dict, actor: ActorDTO) -> dict:
    if staged["source_type"] == "github":
        github = staged["github"]
        return {
            "type": "github",
            "integration_id": github["integration_id"],
            "owner": github["owner"],
            "repository": github["repository"],
            "branch": github["branch"],
            "automation_path": staged.get("automation_path"),
            "manifest_path": staged.get("manifest_path"),
            "workspace_path": github.get("workspace_path"),
            "last_commit_sha": staged.get("commit_sha"),
            "sync_status": "synced",
            "is_active": True,
        }
    upload = staged.get("upload", {})
    return {
        "type": "manual_upload",
        "original_filename": upload.get("original_filename"),
        "uploaded_by_user_id": int(actor.actor_id) if actor.actor_id and actor.actor_id.isdigit() else None,
        "source_sha256": upload.get("source_sha256"),
        "is_active": True,
    }


def _source_repository(staged: dict) -> str | None:
    github = staged.get("github")
    if not github:
        return None
    return f"{github.get('owner')}/{github.get('repository')}"


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "automation"
