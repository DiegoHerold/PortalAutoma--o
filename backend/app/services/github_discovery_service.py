from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.automation_manifest import (
    discover_manifest_paths,
    parse_workspace_manifest,
)
from app.domain.automation_package import build_package
from app.integrations.github.client import GithubAppClient
from app.integrations.storage.factory import get_package_storage
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_source_repository import AutomationSourceRepository
from app.repositories.automation_version_repository import AutomationVersionRepository
from app.repositories.github_integration_repository import GithubIntegrationRepository
from app.services.import_staging_store import create_staging_entry
from modules.catalog.domain.manifest import parse_automation_manifest, validate_entrypoint_on_disk
from modules.catalog.infrastructure.package_validation import ZipPackageValidator

WORKSPACE_MANIFEST_FILENAME = "automation-workspace.yaml"


class GithubDiscoveryService:
    """
    Reads automation-workspace.yaml, walks the repo tree, and validates every
    automation.yaml found under the configured roots — mirrors ManualUploadService
    but sources files from GitHub instead of an uploaded ZIP. Converges on the
    same staging payload shape so AutomationImportService.confirm() is identical
    for both origins (section 3 of the task).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.client = GithubAppClient()
        self.integrations = GithubIntegrationRepository(db)
        self.automations = AutomationRepository(db)
        self.versions = AutomationVersionRepository(db)
        self.sources = AutomationSourceRepository(db)
        self.storage = get_package_storage()

    def _resolve_installation_id(self, integration_id: int) -> int:
        """
        `integration_id` is our local GithubIntegration.id (DB primary key) —
        the GitHub API needs the actual `installation_id` GitHub assigned to
        the installation, a different number. Resolve once per call, never
        pass the DB id straight into GithubAppClient.
        """
        integration = self.integrations.get(integration_id)
        if integration is None:
            raise ValueError("Integração GitHub não encontrada.")
        return integration.installation_id

    def discover(self, integration_id: int, owner: str, repository: str, branch: str) -> list[dict]:
        """Returns discovery items per automation.yaml found (section 5), no side effects."""
        installation_id = self._resolve_installation_id(integration_id)
        try:
            workspace_yaml = self.client.get_file_content(
                installation_id, owner, repository, WORKSPACE_MANIFEST_FILENAME, branch
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"{WORKSPACE_MANIFEST_FILENAME} não encontrado na raiz do repositório: {exc}"
            ) from exc

        workspace, ws_result = parse_workspace_manifest(workspace_yaml)
        if workspace is None:
            raise ValueError(f"{WORKSPACE_MANIFEST_FILENAME} inválido: {'; '.join(ws_result.errors)}")

        tree = self.client.list_repository_tree(installation_id, owner, repository, branch)
        all_paths = [e.path for e in tree if e.type == "blob"]
        manifest_paths = discover_manifest_paths(all_paths, workspace)

        commit_sha = self.client.get_latest_commit_sha(installation_id, owner, repository, branch)

        seen_ids: dict[str, str] = {}
        items: list[dict] = []
        for manifest_path in manifest_paths:
            item = self._describe_manifest(
                installation_id, owner, repository, branch, manifest_path, commit_sha
            )
            key = item.get("key")
            if key and key in seen_ids:
                item["validation_status"] = "invalid"
                item.setdefault("errors", []).append(
                    f"ID duplicado: '{key}' já usado por {seen_ids[key]}."
                )
            elif key:
                seen_ids[key] = manifest_path
            items.append(item)
        return items

    def _describe_manifest(
        self, installation_id: int, owner: str, repo: str, branch: str, manifest_path: str, commit_sha: str
    ) -> dict:
        automation_path = str(Path(manifest_path).parent)
        try:
            raw_yaml = self.client.get_file_content(installation_id, owner, repo, manifest_path, branch)
        except Exception as exc:  # noqa: BLE001
            return {
                "key": None,
                "name": None,
                "version": None,
                "description": None,
                "category": None,
                "path": automation_path,
                "manifest_path": manifest_path,
                "commit_sha": commit_sha,
                "already_imported": False,
                "validation_status": "invalid",
                "errors": [f"Falha ao ler manifesto: {exc}"],
            }

        manifest, result = parse_automation_manifest(raw_yaml)
        errors = list(result.errors)
        already_imported = False
        if manifest is not None:
            automation = self.automations.get_by_key(manifest.id)
            if automation is not None:
                already_imported = self.versions.get_by_version(automation.id, manifest.version) is not None

        return {
            "key": manifest.id if manifest else None,
            "name": manifest.name if manifest else None,
            "version": manifest.version if manifest else None,
            "description": manifest.description if manifest else None,
            "category": manifest.category if manifest else None,
            "runtime_id": manifest.runtime_id if manifest else None,
            "entrypoint_type": manifest.entrypoint_type if manifest else None,
            "path": automation_path,
            "manifest_path": manifest_path,
            "commit_sha": commit_sha,
            "already_imported": already_imported,
            "validation_status": "valid" if manifest and not errors else "invalid",
            "errors": errors,
        }

    def stage_import(
        self,
        integration_id: int,
        owner: str,
        repository: str,
        branch: str,
        manifest_path: str,
        user: User,
    ) -> dict:
        """Downloads one automation folder, validates + packages it, and stages it for confirm()."""
        installation_id = self._resolve_installation_id(integration_id)
        commit_sha = self.client.get_latest_commit_sha(installation_id, owner, repository, branch)
        automation_path = str(Path(manifest_path).parent)

        with tempfile.TemporaryDirectory(prefix="github_import_") as tmp:
            tmp_dir = Path(tmp)
            self.client.download_directory(
                installation_id, owner, repository, branch, automation_path, tmp_dir
            )

            manifest_file = tmp_dir / "automation.yaml"
            if not manifest_file.is_file():
                raise ValueError(f"automation.yaml não encontrado em {automation_path} após o download.")
            raw_manifest_yaml = manifest_file.read_text(encoding="utf-8")

            manifest, result = parse_automation_manifest(raw_manifest_yaml)
            if manifest is None:
                raise ValueError(f"Manifesto inválido: {'; '.join(result.errors)}")

            errors = list(result.errors) + validate_entrypoint_on_disk(manifest, tmp_dir)

            package_zip_path = tmp_dir.parent / f"{tmp_dir.name}-package.zip"
            package_result = build_package(
                source_root=tmp_dir,
                output_zip_path=package_zip_path,
                raw_manifest_yaml=raw_manifest_yaml,
                package_metadata={
                    "source": "github",
                    "repository": f"{owner}/{repository}",
                    "branch": branch,
                    "path": automation_path,
                    "commit_sha": commit_sha,
                    "created_by": user.email,
                },
            )
            package_validation = ZipPackageValidator().validate_zip_package(
                package_result.zip_path,
                self.settings.max_upload_size_mb * 1024 * 1024,
            )
            errors.extend(_issue_to_message(issue) for issue in package_validation["issues"])
            object_key = f"{manifest.id}/{manifest.version}/package.zip"
            stored = self.storage.put(
                self.settings.packages_bucket_name, object_key, package_result.zip_path
            )
            package_zip_path.unlink(missing_ok=True)

        staging_payload = {
            "source_type": "github",
            "manifest": {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "category": manifest.category,
                "schema_version": manifest.schema_version,
                "runtime_id": manifest.runtime_id,
                "runtime_version": manifest.runtime_version,
                "entrypoint_type": manifest.entrypoint_type,
                "entrypoint": manifest.entrypoint,
                "timeout_seconds": manifest.timeout_seconds,
                "raw": manifest.raw,
            },
            "raw_manifest_yaml": raw_manifest_yaml,
            "package": {
                "bucket": stored.bucket,
                "object_key": stored.object_key,
                "size": package_result.size,
                "sha256": package_result.sha256,
                "application_type": package_result.application_type,
                "application_path": package_result.application_path,
            },
            "github": {
                "integration_id": integration_id,
                "owner": owner,
                "repository": repository,
                "branch": branch,
                "workspace_path": WORKSPACE_MANIFEST_FILENAME,
            },
            "errors": errors,
            "automation_path": automation_path,
            "manifest_path": manifest_path,
            "commit_sha": commit_sha,
        }

        if errors:
            # Still return a preview so the user sees exactly why it can't be
            # confirmed, but don't stage it (nothing to confirm safely).
            return {
                "staging_id": None,
                "key": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "category": manifest.category,
                "runtime_id": manifest.runtime_id,
                "entrypoint_type": manifest.entrypoint_type,
                "path": automation_path,
                "manifest_path": manifest_path,
                "commit_sha": commit_sha,
                "source_type": "github",
                "already_imported": False,
                "validation_status": "invalid",
                "errors": errors,
                "package_sha256": package_result.sha256,
                "package_size": package_result.size,
            }

        staging_id = create_staging_entry(staging_payload)
        return {
            "staging_id": staging_id,
            "key": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "category": manifest.category,
            "runtime_id": manifest.runtime_id,
            "entrypoint_type": manifest.entrypoint_type,
            "path": automation_path,
            "manifest_path": manifest_path,
            "commit_sha": commit_sha,
            "source_type": "github",
            "already_imported": False,
            "validation_status": "valid",
            "errors": [],
            "package_sha256": package_result.sha256,
            "package_size": package_result.size,
        }


def _issue_to_message(issue: dict) -> str:
    path = issue.get("path")
    message = issue.get("message", "Package validation failed.")
    code = issue.get("code", "PACKAGE_VALIDATION_FAILED")
    return f"{code}: {path}: {message}" if path else f"{code}: {message}"
