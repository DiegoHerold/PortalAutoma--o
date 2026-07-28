"""
Builds the immutable package ZIP for an automation version, from either a
GitHub download or a manual ZIP upload — both paths converge here so the
Automation Agent never needs to know the origin (see docs/automation-package.md).

Pure filesystem + zipfile logic, no DB dependency, unit tested in
tests/domain/test_automation_package.py.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.domain.automation_manifest import AutomationManifest

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


def is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info") for part in relative_path.parts):
        return True
    return any(fnmatch.fnmatch(relative_path.name, pattern) for pattern in EXCLUDED_FILE_GLOBS)


@dataclass
class PackageResult:
    zip_path: Path
    size: int
    sha256: str
    application_type: str  # "source" | "wheel"
    application_path: str


def _iter_included_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if is_excluded(rel):
            continue
        yield path, rel


def build_package(
    *,
    source_root: Path,
    output_zip_path: Path,
    raw_manifest_yaml: str,
    package_metadata: dict,
) -> PackageResult:
    """
    source_root must contain automation.yaml at its top level (callers are
    responsible for locating/normalizing to that shape first — see
    manual_upload_service / github_import_service).
    """
    manifest_path = source_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ValueError(f"{MANIFEST_FILENAME} não encontrado em {source_root}")

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
                if rel.name == MANIFEST_FILENAME:
                    continue
                zf.write(path, arcname=str(Path("application") / rel))
        else:
            src_dir = source_root / "src"
            if src_dir.is_dir():
                for path, rel in _iter_included_files(src_dir):
                    zf.write(path, arcname=str(Path("application") / rel))
            # else: no src/ layout found — package still valid if entrypoint
            # validation was skipped/soft; application/ will simply be empty.

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
        # package_sha256 of the metadata itself is meaningless (chicken-and-egg);
        # the *artifact's* sha256 is computed by the caller over the final zip
        # and stored in AutomationVersion.artifact_sha256, not inside the zip.
        zf.writestr(PACKAGE_METADATA_FILENAME, json.dumps(metadata, indent=2, ensure_ascii=False))

    digest = hashlib.sha256()
    with output_zip_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)

    return PackageResult(
        zip_path=output_zip_path,
        size=output_zip_path.stat().st_size,
        sha256=digest.hexdigest(),
        application_type=application_type,
        application_path=application_path,
    )


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    """
    Extracts a ZIP after validating every member stays within `destination`
    (blocks path traversal via `..` or absolute paths) — never extracts a
    member outside the target directory.
    """
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = (destination / member.filename).resolve()
            if not str(member_path).startswith(str(destination) + "/") and member_path != destination:
                raise ValueError(f"Entrada de ZIP insegura (path traversal): {member.filename}")
        zf.extractall(destination)


def find_single_root_dir(extracted_root: Path) -> Path:
    """
    If the extracted ZIP contains exactly one top-level directory (and no
    top-level files besides hidden/system ones), return it — this is the
    common "one root folder" shape from GitHub-style ZIP downloads. Otherwise
    returns extracted_root unchanged.
    """
    entries = [p for p in extracted_root.iterdir() if not p.name.startswith(".")]
    dirs = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]
    if len(dirs) == 1 and not files:
        return dirs[0]
    return extracted_root


def cleanup(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
