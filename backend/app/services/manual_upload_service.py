from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.automation_manifest import locate_single_manifest
from app.domain.automation_package import build_package, find_single_root_dir, safe_extract_zip
from app.integrations.storage.factory import get_package_storage
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_version_repository import AutomationVersionRepository
from app.services.import_staging_store import create_staging_entry
from modules.catalog.domain.manifest import parse_automation_manifest, validate_entrypoint_on_disk
from modules.catalog.infrastructure.package_validation import ZipPackageValidator


class ManualUploadError(ValueError):
    """Raised for any rejection during ZIP import (missing manifest, too large, traversal, ...)."""


def _hash_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


class ManualUploadService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.automations = AutomationRepository(db)
        self.versions = AutomationVersionRepository(db)
        self.storage = get_package_storage()

    def import_from_zip(self, upload: UploadFile, user: User) -> dict:
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        with tempfile.TemporaryDirectory(prefix="automation_upload_") as tmp:
            tmp_dir = Path(tmp)
            raw_zip_path = tmp_dir / "upload.zip"

            size = 0
            with raw_zip_path.open("wb") as out:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ManualUploadError(
                            f"Arquivo excede o limite de {self.settings.max_upload_size_mb} MB."
                        )
                    out.write(chunk)

            if size == 0:
                raise ManualUploadError("Arquivo vazio.")

            with raw_zip_path.open("rb") as fh:
                source_sha256 = _hash_stream(fh)

            extraction_dir = tmp_dir / "extracted"
            try:
                safe_extract_zip(raw_zip_path, extraction_dir)
            except ValueError as exc:
                raise ManualUploadError(str(exc)) from exc

            automation_root = find_single_root_dir(extraction_dir)

            all_paths = [
                str(p.relative_to(automation_root)) for p in automation_root.rglob("*") if p.is_file()
            ]
            manifest_rel_path = locate_single_manifest(all_paths)
            if manifest_rel_path is None:
                raise ManualUploadError(
                    "automation.yaml não encontrado no ZIP. A importação manual exige um manifesto válido."
                )
            # If the manifest itself is nested one level deeper (shouldn't normally
            # happen after find_single_root_dir, but handle defensively).
            manifest_dir = automation_root / Path(manifest_rel_path).parent
            manifest_path = manifest_dir / "automation.yaml"
            raw_manifest_yaml = manifest_path.read_text(encoding="utf-8")

            manifest, validation = parse_automation_manifest(raw_manifest_yaml)
            errors = list(validation.errors)

            if manifest is not None:
                errors.extend(validate_entrypoint_on_disk(manifest, manifest_dir))

            validation_status = "valid" if not errors else "invalid"

            already_imported = False
            if manifest is not None:
                existing_automation = self.automations.get_by_key(manifest.id)
                if existing_automation is not None:
                    already_imported = (
                        self.versions.get_by_version(existing_automation.id, manifest.version) is not None
                    )

            package_result = None
            if manifest is not None:
                package_zip_path = tmp_dir / "package.zip"
                package_result = build_package(
                    source_root=manifest_dir,
                    output_zip_path=package_zip_path,
                    raw_manifest_yaml=raw_manifest_yaml,
                    package_metadata={
                        "source": "manual_upload",
                        "original_filename": upload.filename,
                        "created_by": user.email,
                    },
                )
                package_validation = ZipPackageValidator().validate_zip_package(package_result.zip_path, max_bytes)
                errors.extend(_issue_to_message(issue) for issue in package_validation["issues"])
                object_key = f"{manifest.id}/{manifest.version}/package.zip"
                stored = self.storage.put(
                    self.settings.packages_bucket_name, object_key, package_result.zip_path
                )

            validation_status = "valid" if not errors else "invalid"

            if manifest is None or package_result is None:
                # Manifest present but too broken to even parse — surface errors,
                # nothing is staged/stored.
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
                    "manifest_path": manifest_rel_path,
                    "commit_sha": None,
                    "source_type": "manual_upload",
                    "already_imported": False,
                    "validation_status": "invalid",
                    "errors": errors,
                    "package_sha256": "",
                    "package_size": 0,
                }

            staging_payload = {
                "source_type": "manual_upload",
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
                "upload": {
                    "original_filename": upload.filename,
                    "source_sha256": source_sha256,
                },
                "errors": errors,
                "automation_path": None,
                "manifest_path": manifest_rel_path,
                "commit_sha": None,
            }

            staging_id = None
            if validation_status == "valid" and not already_imported:
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
                "path": None,
                "manifest_path": manifest_rel_path,
                "commit_sha": None,
                "source_type": "manual_upload",
                "already_imported": already_imported,
                "validation_status": validation_status,
                "errors": errors,
                "package_sha256": package_result.sha256,
                "package_size": package_result.size,
            }


def _issue_to_message(issue: dict) -> str:
    path = issue.get("path")
    message = issue.get("message", "Package validation failed.")
    code = issue.get("code", "PACKAGE_VALIDATION_FAILED")
    return f"{code}: {path}: {message}" if path else f"{code}: {message}"
