"""Build immutable certification package .zip files from
`automation-agent/certification/<name>/` source directories.

The zip layout mirrors `automation-agent/examples/background-python/`
exactly: `automation.json` at the archive root plus an `automation/`
directory holding the entrypoint module. That is the layout
`Agent.Infrastructure/Stores/PackageStore.cs::FindManifest` looks for and
that `RuntimeLauncher.BuildPythonFunction` expects on `sys.path`.

Packages are content-addressed: the same source directory always produces
the same zip bytes (fixed file order, fixed timestamps), so re-running
`certification prepare` does not produce a different SHA-256 unless the
package source actually changed — that is what makes package provisioning
idempotent (docs/certification-harness.md, "Idempotência do seed").
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass

# Fixed timestamp so byte-identical source always produces a byte-identical
# zip (DOS date/time tuple: 1980-01-01 00:00:00, the zip format minimum).
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

# Same exclusion list as the Catalog's own `build_package` for
# GitHub-imported packages (see docs/automation-package.md), so
# certification packages are built the same way real packages are.
_EXCLUDED_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", "tests", ".pytest_cache", "node_modules"}
_EXCLUDED_FILE_SUFFIXES = (".pyc", ".pyo")


@dataclass(frozen=True)
class BuiltPackage:
    zip_bytes: bytes
    sha256: str
    size_bytes: int
    file_name: str


def _iter_files_sorted(root: str) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(_EXCLUDED_FILE_SUFFIXES):
                continue
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files.append(rel)
    return sorted(files)


def build_package_zip(
    source_dir: str,
    file_name: str,
    *,
    automation_yaml: str,
    manifest_version: str,
) -> BuiltPackage:
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Certification package source not found: {source_dir}")
    manifest_path = os.path.join(source_dir, "automation.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"automation.json missing in {source_dir}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_zip_entry(archive, "automation.yaml", automation_yaml.encode("utf-8"))
        for rel_path in _iter_files_sorted(source_dir):
            if rel_path == "automation.yaml":
                continue
            full_path = os.path.join(source_dir, rel_path.replace("/", os.sep))
            with open(full_path, "rb") as handle:
                content = handle.read()
            if rel_path == "automation.json":
                content = _with_manifest_version(content, manifest_version)
            _write_zip_entry(archive, rel_path, content)

    zip_bytes = buffer.getvalue()
    sha256 = hashlib.sha256(zip_bytes).hexdigest()
    return BuiltPackage(zip_bytes=zip_bytes, sha256=sha256, size_bytes=len(zip_bytes), file_name=file_name)


def write_package_zip(
    source_dir: str,
    file_name: str,
    output_path: str,
    *,
    automation_yaml: str,
    manifest_version: str,
) -> BuiltPackage:
    built = build_package_zip(
        source_dir,
        file_name,
        automation_yaml=automation_yaml,
        manifest_version=manifest_version,
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as handle:
        handle.write(built.zip_bytes)
    return built


def _write_zip_entry(archive: zipfile.ZipFile, rel_path: str, content: bytes) -> None:
    info = zipfile.ZipInfo(rel_path, date_time=_FIXED_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, content)


def _with_manifest_version(content: bytes, version: str) -> bytes:
    manifest = json.loads(content.decode("utf-8"))
    manifest["version"] = version
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
