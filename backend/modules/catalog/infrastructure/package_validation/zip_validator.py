from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any

from modules.catalog.domain.manifest import parse_automation_manifest, validate_manifest_package_paths

MAX_FILES = 5000
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_RATIO = 100
FORBIDDEN_EXTENSIONS = {".exe", ".bat", ".cmd", ".msi", ".ps1", ".vbs", ".js"}
RESERVED_WINDOWS_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


class ZipPackageValidator:
    def validate_zip_package(self, file_path, max_size_bytes: int) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        if file_path.stat().st_size > max_size_bytes:
            issues.append(_issue("PACKAGE_TOO_LARGE", "", "Package exceeds the configured maximum size."))
        try:
            with zipfile.ZipFile(file_path) as zf:
                infos = zf.infolist()
                if len(infos) > MAX_FILES:
                    issues.append(_issue("PACKAGE_TOO_MANY_FILES", "", "Package contains too many files."))
                names = [info.filename.replace("\\", "/") for info in infos if not info.is_dir()]
                total_uncompressed = sum(info.file_size for info in infos)
                compressed_size = max(1, sum(info.compress_size for info in infos))
                if total_uncompressed / compressed_size > MAX_UNCOMPRESSED_RATIO:
                    issues.append(_issue("PACKAGE_ZIP_BOMB_RISK", "", "Package compression ratio is suspicious."))

                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if _is_symlink(info):
                        issues.append(_issue("PACKAGE_SYMLINK_FORBIDDEN", name, "Symlinks are not allowed in packages."))
                    if not _is_safe_package_path(name):
                        issues.append(_issue("PACKAGE_UNSAFE_PATH", name, "Package path must be relative and safe."))
                    if info.file_size > MAX_FILE_SIZE_BYTES:
                        issues.append(_issue("PACKAGE_FILE_TOO_LARGE", name, "A package file exceeds the per-file size limit."))
                    suffix = PurePosixPath(name).suffix.lower()
                    if suffix in FORBIDDEN_EXTENSIONS:
                        issues.append(_issue("PACKAGE_FORBIDDEN_EXTENSION", name, "Executable/script extension is not allowed in this static package."))

                if "automation.yaml" not in names:
                    issues.append(_issue("PACKAGE_MANIFEST_MISSING", "automation.yaml", "automation.yaml is required at package root."))
                    return {"valid": False, "issues": issues}

                raw_manifest = zf.read("automation.yaml").decode("utf-8")
                manifest, manifest_result = parse_automation_manifest(raw_manifest)
                issues.extend(manifest_result.to_payload())
                if manifest is not None:
                    issues.extend(validate_manifest_package_paths(manifest, set(names)).to_payload())
                if "checksums.json" in names:
                    issues.extend(_validate_checksums(zf, names))
        except (zipfile.BadZipFile, UnicodeDecodeError, KeyError) as exc:
            issues.append(_issue("PACKAGE_INVALID_ZIP", "", f"Invalid package zip: {exc}"))
        return {"valid": not issues, "issues": issues}


def _validate_checksums(zf: zipfile.ZipFile, names: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        payload = json.loads(zf.read("checksums.json"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [_issue("PACKAGE_CHECKSUMS_INVALID_JSON", "checksums.json", f"checksums.json is invalid: {exc}")]
    if payload.get("algorithm") != "sha256":
        issues.append(_issue("PACKAGE_CHECKSUMS_ALGORITHM_UNSUPPORTED", "checksums.json", "Only sha256 checksums are supported."))
        return issues
    files = payload.get("files")
    if not isinstance(files, dict):
        return [_issue("PACKAGE_CHECKSUMS_FILES_INVALID", "checksums.json", "checksums.files must be an object.")]
    for path, expected in files.items():
        if path not in names:
            issues.append(_issue("PACKAGE_CHECKSUM_FILE_MISSING", path, "Checksum references a missing file."))
            continue
        actual = hashlib.sha256(zf.read(path)).hexdigest()
        if actual != expected:
            issues.append(_issue("PACKAGE_CHECKSUM_MISMATCH", path, "Checksum does not match file content."))
    return issues


def _is_safe_package_path(value: str) -> bool:
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        return False
    if ":" in value or value.startswith("\\"):
        return False
    return all(part.split(".")[0].lower() not in RESERVED_WINDOWS_NAMES for part in path.parts)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _issue(code: str, path: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "path": path, "message": message, "details": details or {}}
