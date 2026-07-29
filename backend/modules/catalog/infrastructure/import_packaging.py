from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from fastapi import UploadFile
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.github.client import GithubAppClient
from infrastructure.storage.factory import get_package_storage
from modules.catalog.domain.manifest import (
    discover_manifest_paths,
    locate_single_manifest,
    parse_automation_manifest,
    parse_workspace_manifest,
    validate_entrypoint_on_disk,
)
from modules.catalog.domain.package import build_package, find_single_root_dir, safe_extract_zip
from modules.catalog.infrastructure.import_staging_store import create_staging_entry
from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord, CatalogAutomationVersionRecord, GithubIntegrationRecord
from modules.catalog.infrastructure.package_validation import ZipPackageValidator

WORKSPACE_MANIFEST_FILENAME = "automation-workspace.yaml"


class AutomationImportPackagingError(ValueError):
    pass


class CatalogImportPackagingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage = get_package_storage()

    def import_from_zip(self, upload: UploadFile, user: Any) -> dict[str, Any]:
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        with tempfile.TemporaryDirectory(prefix="automation_upload_") as tmp:
            tmp_dir = Path(tmp)
            raw_zip_path = tmp_dir / "upload.zip"
            size = _copy_upload(upload, raw_zip_path, max_bytes)
            if size == 0:
                raise AutomationImportPackagingError("Arquivo vazio.")
            with raw_zip_path.open("rb") as fh:
                source_sha256 = _hash_stream(fh)

            extraction_dir = tmp_dir / "extracted"
            try:
                safe_extract_zip(raw_zip_path, extraction_dir)
            except ValueError as exc:
                raise AutomationImportPackagingError(str(exc)) from exc

            automation_root = find_single_root_dir(extraction_dir)
            all_paths = [str(path.relative_to(automation_root)) for path in automation_root.rglob("*") if path.is_file()]
            manifest_rel_path = locate_single_manifest(all_paths)
            if manifest_rel_path is None:
                raise AutomationImportPackagingError("automation.yaml nao encontrado no ZIP. A importacao manual exige um manifesto valido.")
            manifest_dir = automation_root / Path(manifest_rel_path).parent
            raw_manifest_yaml = (manifest_dir / "automation.yaml").read_text(encoding="utf-8")
            manifest, validation = parse_automation_manifest(raw_manifest_yaml)
            errors = list(validation.errors)
            if manifest is not None:
                errors.extend(validate_entrypoint_on_disk(manifest, manifest_dir))

            package_result = None
            stored = None
            if manifest is not None:
                package_zip_path = tmp_dir / "package.zip"
                package_result = build_package(
                    source_root=manifest_dir,
                    output_zip_path=package_zip_path,
                    raw_manifest_yaml=raw_manifest_yaml,
                    package_metadata={"source": "manual_upload", "original_filename": upload.filename, "created_by": getattr(user, "email", None)},
                )
                package_validation = ZipPackageValidator().validate_zip_package(package_result.zip_path, max_bytes)
                errors.extend(_issue_to_message(issue) for issue in package_validation["issues"])
                stored = self.storage.put(self.settings.packages_bucket_name, f"{manifest.id}/{manifest.version}/package.zip", package_result.zip_path)

            if manifest is None or package_result is None or stored is None:
                return _preview(
                    source_type="manual_upload",
                    validation_status="invalid",
                    errors=errors,
                    manifest_path=manifest_rel_path,
                )

            already_imported = _already_imported(self.db, manifest.id, manifest.version)
            staging_id = None
            if not errors and not already_imported:
                staging_id = create_staging_entry(
                    {
                        "source_type": "manual_upload",
                        "manifest": _manifest_payload(manifest),
                        "raw_manifest_yaml": raw_manifest_yaml,
                        "package": _package_payload(stored, package_result),
                        "upload": {"original_filename": upload.filename, "source_sha256": source_sha256},
                        "errors": errors,
                        "automation_path": None,
                        "manifest_path": manifest_rel_path,
                        "commit_sha": None,
                    }
                )

            return _preview_from_manifest(
                manifest,
                source_type="manual_upload",
                staging_id=staging_id,
                manifest_path=manifest_rel_path,
                already_imported=already_imported,
                validation_status="valid" if not errors else "invalid",
                errors=errors,
                package_sha256=package_result.sha256,
                package_size=package_result.size,
            )

    def discover_github(self, integration_id: int, owner: str, repository: str, branch: str) -> list[dict[str, Any]]:
        installation_id = _resolve_installation_id(self.db, integration_id)
        client = GithubAppClient()
        try:
            workspace_yaml = client.get_file_content(installation_id, owner, repository, WORKSPACE_MANIFEST_FILENAME, branch)
            workspace, workspace_result = parse_workspace_manifest(workspace_yaml)
            if workspace is None:
                raise AutomationImportPackagingError(f"{WORKSPACE_MANIFEST_FILENAME} invalido: {'; '.join(workspace_result.errors)}")
            tree = client.list_repository_tree(installation_id, owner, repository, branch)
            all_paths = [entry.path for entry in tree if entry.type == "blob"]
            manifest_paths = discover_manifest_paths(all_paths, workspace)
            commit_sha = client.get_latest_commit_sha(installation_id, owner, repository, branch)
            seen_keys: dict[str, str] = {}
            items: list[dict[str, Any]] = []
            for manifest_path in manifest_paths:
                item = self._describe_github_manifest(client, installation_id, owner, repository, branch, manifest_path, commit_sha)
                key = item.get("key")
                if key and key in seen_keys:
                    item["validation_status"] = "invalid"
                    item.setdefault("errors", []).append(f"ID duplicado: '{key}' ja usado por {seen_keys[key]}.")
                elif key:
                    seen_keys[key] = manifest_path
                items.append(item)
            return items
        finally:
            client.close()

    def stage_github_import(self, integration_id: int, owner: str, repository: str, branch: str, manifest_path: str, user: Any) -> dict[str, Any]:
        installation_id = _resolve_installation_id(self.db, integration_id)
        client = GithubAppClient()
        try:
            commit_sha = client.get_latest_commit_sha(installation_id, owner, repository, branch)
            automation_path = str(Path(manifest_path).parent)
            with tempfile.TemporaryDirectory(prefix="github_import_") as tmp:
                tmp_dir = Path(tmp)
                client.download_directory(installation_id, owner, repository, branch, automation_path, tmp_dir)
                manifest_file = tmp_dir / "automation.yaml"
                if not manifest_file.is_file():
                    raise AutomationImportPackagingError(f"automation.yaml nao encontrado em {automation_path} apos o download.")
                raw_manifest_yaml = manifest_file.read_text(encoding="utf-8")
                manifest, validation = parse_automation_manifest(raw_manifest_yaml)
                if manifest is None:
                    raise AutomationImportPackagingError(f"Manifesto invalido: {'; '.join(validation.errors)}")
                errors = list(validation.errors) + validate_entrypoint_on_disk(manifest, tmp_dir)
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
                        "created_by": getattr(user, "email", None),
                    },
                )
                package_validation = ZipPackageValidator().validate_zip_package(package_result.zip_path, self.settings.max_upload_size_mb * 1024 * 1024)
                errors.extend(_issue_to_message(issue) for issue in package_validation["issues"])
                stored = self.storage.put(self.settings.packages_bucket_name, f"{manifest.id}/{manifest.version}/package.zip", package_result.zip_path)

            staging_id = None
            if not errors:
                staging_id = create_staging_entry(
                    {
                        "source_type": "github",
                        "manifest": _manifest_payload(manifest),
                        "raw_manifest_yaml": raw_manifest_yaml,
                        "package": _package_payload(stored, package_result),
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
                )
            return _preview_from_manifest(
                manifest,
                source_type="github",
                staging_id=staging_id,
                path=automation_path,
                manifest_path=manifest_path,
                commit_sha=commit_sha,
                already_imported=_already_imported(self.db, manifest.id, manifest.version),
                validation_status="valid" if not errors else "invalid",
                errors=errors,
                package_sha256=package_result.sha256,
                package_size=package_result.size,
            )
        finally:
            client.close()

    def _describe_github_manifest(self, client: GithubAppClient, installation_id: int, owner: str, repo: str, branch: str, manifest_path: str, commit_sha: str) -> dict[str, Any]:
        automation_path = str(Path(manifest_path).parent)
        try:
            raw_yaml = client.get_file_content(installation_id, owner, repo, manifest_path, branch)
        except Exception as exc:
            return _preview(source_type="github", validation_status="invalid", errors=[f"Falha ao ler manifesto: {exc}"], path=automation_path, manifest_path=manifest_path, commit_sha=commit_sha)
        manifest, result = parse_automation_manifest(raw_yaml)
        errors = list(result.errors)
        if manifest is None:
            return _preview(source_type="github", validation_status="invalid", errors=errors, path=automation_path, manifest_path=manifest_path, commit_sha=commit_sha)
        return _preview_from_manifest(
            manifest,
            source_type="github",
            path=automation_path,
            manifest_path=manifest_path,
            commit_sha=commit_sha,
            already_imported=_already_imported(self.db, manifest.id, manifest.version),
            validation_status="valid" if not errors else "invalid",
            errors=errors,
        )


def _copy_upload(upload: UploadFile, target: Path, max_bytes: int) -> int:
    size = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise AutomationImportPackagingError("Arquivo excede o limite de upload configurado.")
            out.write(chunk)
    return size


def _hash_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _resolve_installation_id(db: Session, integration_id: int) -> int:
    integration = db.get(GithubIntegrationRecord, integration_id)
    if integration is None:
        raise AutomationImportPackagingError("Integracao GitHub nao encontrada.")
    return integration.installation_id


def _already_imported(db: Session, automation_key: str, version: str) -> bool:
    automation = db.query(CatalogAutomationRecord).filter(CatalogAutomationRecord.key == automation_key).first()
    if automation is None:
        return False
    return (
        db.query(CatalogAutomationVersionRecord)
        .filter(CatalogAutomationVersionRecord.automation_id == automation.id, CatalogAutomationVersionRecord.version == version)
        .first()
        is not None
    )


def _manifest_payload(manifest) -> dict[str, Any]:
    return {
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
    }


def _package_payload(stored, package_result) -> dict[str, Any]:
    return {
        "bucket": stored.bucket,
        "object_key": stored.object_key,
        "size": package_result.size,
        "sha256": package_result.sha256,
        "application_type": package_result.application_type,
        "application_path": package_result.application_path,
    }


def _preview_from_manifest(manifest, **overrides: Any) -> dict[str, Any]:
    return {
        "staging_id": None,
        "key": manifest.id,
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "category": manifest.category,
        "runtime_id": manifest.runtime_id,
        "entrypoint_type": manifest.entrypoint_type,
        "path": None,
        "manifest_path": None,
        "commit_sha": None,
        "source_type": "manual_upload",
        "already_imported": False,
        "validation_status": "valid",
        "errors": [],
        "package_sha256": "",
        "package_size": 0,
        **overrides,
    }


def _preview(**overrides: Any) -> dict[str, Any]:
    return {
        "staging_id": None,
        "key": None,
        "name": None,
        "version": None,
        "description": None,
        "category": None,
        "runtime_id": None,
        "entrypoint_type": None,
        "path": None,
        "manifest_path": None,
        "commit_sha": None,
        "source_type": "manual_upload",
        "already_imported": False,
        "validation_status": "invalid",
        "errors": [],
        "package_sha256": "",
        "package_size": 0,
        **overrides,
    }


def _issue_to_message(issue: dict) -> str:
    path = issue.get("path")
    message = issue.get("message", "Package validation failed.")
    code = issue.get("code", "PACKAGE_VALIDATION_FAILED")
    return f"{code}: {path}: {message}" if path else f"{code}: {message}"
