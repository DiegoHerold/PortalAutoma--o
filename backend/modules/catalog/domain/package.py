from __future__ import annotations

import fnmatch
import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.catalog.domain.states import AutomationPackageStatus
from modules.catalog.domain.value_objects import ContentHash


@dataclass(frozen=True)
class PackageValidationIssue:
    code: str
    path: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PackageValidationResult:
    issues: tuple[PackageValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def to_payload(self) -> dict[str, Any]:
        return {
            "valid": self.is_valid,
            "issues": [
                {
                    "code": issue.code,
                    "path": issue.path,
                    "message": issue.message,
                    "details": issue.details,
                }
                for issue in self.issues
            ],
        }


@dataclass(frozen=True)
class AutomationPackage:
    id: str
    automation_version_id: str
    stored_object_id: str
    package_format: str
    file_name: str
    size_bytes: int
    sha256: str
    status: AutomationPackageStatus
    signature: str | None = None
    signature_algorithm: str | None = None
    signing_key_id: str | None = None
    validation_result: dict[str, Any] | None = None
    created_at: datetime | None = None
    validated_at: datetime | None = None
    published_at: datetime | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        ContentHash("sha256", self.sha256)
        if self.size_bytes <= 0:
            raise ValueError("Package size must be positive.")
        if self.package_format not in {"zip"}:
            raise ValueError("Only zip automation packages are supported.")

    @property
    def is_immutable(self) -> bool:
        return self.status in {
            AutomationPackageStatus.PUBLISHED,
            AutomationPackageStatus.BLOCKED,
        }


EXCLUDED_DIR_NAMES = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "tests",
    "dist",
    "build",
}
EXCLUDED_FILE_GLOBS = ["*.pyc", "*.log", "*.egg-info", ".env", ".env.*"]
PACKAGE_METADATA_FILENAME = "package-metadata.json"
MANIFEST_FILENAME = "automation.yaml"


@dataclass(frozen=True)
class PackageBuildResult:
    zip_path: Path
    size: int
    sha256: str
    application_type: str
    application_path: str


def is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info") for part in relative_path.parts):
        return True
    return any(fnmatch.fnmatch(relative_path.name, pattern) for pattern in EXCLUDED_FILE_GLOBS)


def build_package(
    *,
    source_root: Path,
    output_zip_path: Path,
    raw_manifest_yaml: str,
    package_metadata: dict,
) -> PackageBuildResult:
    manifest_path = source_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ValueError(f"{MANIFEST_FILENAME} not found in {source_root}")

    already_packaged = (source_root / "application").is_dir()
    application_type = "source"
    application_path = "application"

    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    if output_zip_path.exists():
        output_zip_path.unlink()

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_FILENAME, raw_manifest_yaml)

        if already_packaged:
            app_dir = source_root / "application"
            wheel_files = list(app_dir.glob("*.whl"))
            application_type = "wheel" if wheel_files else "source"
            for path, rel in _iter_included_files(app_dir):
                if rel.name != MANIFEST_FILENAME:
                    zf.write(path, arcname=str(Path("application") / rel))
        else:
            src_dir = source_root / "src"
            if src_dir.is_dir():
                for path, rel in _iter_included_files(src_dir):
                    zf.write(path, arcname=str(Path("application") / rel))

        for extra_name in ("pyproject.toml", "README.md", "requirements.txt"):
            extra_path = source_root / extra_name
            if extra_path.is_file():
                zf.write(extra_path, arcname=extra_name)

        resources_dir = source_root / "resources"
        if resources_dir.is_dir():
            for path, rel in _iter_included_files(resources_dir):
                zf.write(path, arcname=str(Path("resources") / rel))

        metadata = {
            **package_metadata,
            "created_at": package_metadata.get("created_at") or datetime.now(UTC).isoformat(),
        }
        zf.writestr(PACKAGE_METADATA_FILENAME, json.dumps(metadata, indent=2, ensure_ascii=False))

    digest = hashlib.sha256()
    with output_zip_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)

    return PackageBuildResult(
        zip_path=output_zip_path,
        size=output_zip_path.stat().st_size,
        sha256=digest.hexdigest(),
        application_type=application_type,
        application_path=application_path,
    )


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(destination)
            except ValueError as exc:
                raise ValueError(f"Unsafe ZIP entry path: {member.filename}") from exc
            if member_path == destination:
                raise ValueError(f"Unsafe ZIP entry path: {member.filename}")
        zf.extractall(destination)


def find_single_root_dir(extracted_root: Path) -> Path:
    entries = [path for path in extracted_root.iterdir() if not path.name.startswith(".")]
    directories = [path for path in entries if path.is_dir()]
    files = [path for path in entries if path.is_file()]
    if len(directories) == 1 and not files:
        return directories[0]
    return extracted_root


def _iter_included_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if is_excluded(relative):
            continue
        yield path, relative
