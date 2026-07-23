from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.constants import AutomationVersionStatus
from app.models.automation import Automation
from app.models.automation_source import AutomationSource
from app.models.automation_version import AutomationVersion
from app.models.category import Category
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_source_repository import AutomationSourceRepository
from app.repositories.automation_version_repository import AutomationVersionRepository
from app.repositories.category_repository import CategoryRepository
from app.services.audit_service import AuditService
from app.services.import_staging_store import delete_staging_entry, get_staging_entry
from app.utils.datetime import utcnow


class DuplicateVersionError(Exception):
    """Raised when confirming a staged import whose (automation_id, version) already exists."""


class StagingNotFoundError(Exception):
    """Raised when a staging_id is missing or has expired."""


class AutomationImportService:
    """
    Shared confirm step for both import origins (GitHub discovery and manual
    ZIP upload). Both producers call `stage(...)` with an already-built,
    already-stored package; this service only ever creates the
    Automation/AutomationSource/AutomationVersion rows on `confirm(...)`.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.automations = AutomationRepository(db)
        self.sources = AutomationSourceRepository(db)
        self.versions = AutomationVersionRepository(db)
        self.categories = CategoryRepository(db)
        self.audit = AuditService(db)

    def _slugify(self, value: str) -> str:
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "automation"

    def _resolve_category(self, category_name: str | None, category_id: int | None) -> Category:
        if category_id is not None:
            category = self.categories.get(category_id)
            if category is None:
                raise ValueError("Categoria informada não encontrada.")
            return category
        if category_name:
            existing = next(
                (c for c in self.categories.list_all() if c.name.lower() == category_name.lower()), None
            )
            if existing:
                return existing
            category = Category(name=category_name, slug=self._slugify(category_name), is_active=True)
            return self.categories.create(category)
        raise ValueError("Informe category_id ou uma categoria no manifesto.")

    def confirm(self, staging_id: str, user: User, category_id: int | None = None) -> AutomationVersion:
        staged = get_staging_entry(staging_id)
        if staged is None:
            raise StagingNotFoundError(f"Importação {staging_id} não encontrada ou expirada.")

        manifest = staged["manifest"]
        automation_key = manifest["id"]

        automation = self._find_or_create_automation(manifest, automation_key, category_id, user)

        existing_version = self.versions.get_by_version(automation.id, manifest["version"])
        if existing_version is not None:
            raise DuplicateVersionError(
                f"A versão {manifest['version']} já existe para '{automation_key}' "
                f"(criada em {existing_version.created_at}). Publique com um número de versão novo."
            )

        source = self._create_source(automation.id, staged, user)

        version = AutomationVersion(
            automation_id=automation.id,
            source_id=source.id,
            version=manifest["version"],
            manifest=manifest["raw"],
            manifest_schema_version=manifest.get("schema_version", 1),
            runtime_id=manifest["runtime_id"],
            runtime_version=manifest.get("runtime_version"),
            entrypoint_type=manifest["entrypoint_type"],
            entrypoint=manifest["entrypoint"],
            application_type=staged["package"]["application_type"],
            application_path=staged["package"]["application_path"],
            artifact_bucket=staged["package"]["bucket"],
            artifact_object_key=staged["package"]["object_key"],
            artifact_size=staged["package"]["size"],
            artifact_sha256=staged["package"]["sha256"],
            source_commit_sha=staged.get("commit_sha"),
            source_path=staged.get("automation_path"),
            status=AutomationVersionStatus.READY,
            validation_errors=staged.get("errors") or None,
            published_at=utcnow(),
        )
        self.versions.create(version)

        self.audit.record(
            "automation_version_imported",
            actor_email=user.email,
            actor_type="user",
            entity_type="automation_version",
            entity_id=str(version.id),
            details=f"{automation_key}@{manifest['version']} via {staged['source_type']}",
            after={
                "automation_id": automation.id,
                "version": manifest["version"],
                "source_type": staged["source_type"],
                "artifact_sha256": staged["package"]["sha256"],
            },
        )
        self.db.commit()
        delete_staging_entry(staging_id)
        self.db.refresh(version)
        return version

    def discard(self, staging_id: str) -> None:
        delete_staging_entry(staging_id)

    def _find_or_create_automation(
        self, manifest: dict, automation_key: str, category_id: int | None, user: User
    ) -> Automation:
        automation = self.automations.get_by_key(automation_key)
        if automation is not None:
            return automation

        category = self._resolve_category(manifest.get("category"), category_id)
        slug_base = self._slugify(manifest["name"])
        slug = slug_base
        suffix = 1
        while self.automations.get_by_slug(slug) is not None:
            suffix += 1
            slug = f"{slug_base}-{suffix}"

        automation = Automation(
            name=manifest["name"],
            slug=slug,
            key=automation_key,
            description=manifest.get("description"),
            category_id=category.id,
            executor_type="python_script",
            default_priority="normal",
            timeout_seconds=manifest.get("timeout_seconds", 300),
            max_retries=0,
            is_active=True,
        )
        automation = self.automations.create(automation)
        self.audit.record(
            "automation_registered_from_catalog",
            actor_email=user.email,
            actor_type="user",
            entity_type="automation",
            entity_id=str(automation.id),
            details=automation_key,
        )
        return automation

    def _create_source(self, automation_id: int, staged: dict, user: User) -> AutomationSource:
        source_type = staged["source_type"]
        now = utcnow()
        if source_type == "github":
            gh = staged["github"]
            source = AutomationSource(
                automation_id=automation_id,
                type="github",
                integration_id=gh["integration_id"],
                owner=gh["owner"],
                repository=gh["repository"],
                branch=gh["branch"],
                automation_path=staged.get("automation_path"),
                manifest_path=staged.get("manifest_path"),
                workspace_path=gh.get("workspace_path"),
                last_commit_sha=staged.get("commit_sha"),
                last_synced_at=now,
                sync_status="synced",
                is_active=True,
            )
        else:
            upload = staged.get("upload", {})
            source = AutomationSource(
                automation_id=automation_id,
                type="manual_upload",
                original_filename=upload.get("original_filename"),
                uploaded_by_user_id=user.id,
                uploaded_at=now,
                source_sha256=upload.get("source_sha256"),
                is_active=True,
            )
        return self.sources.create(source)
