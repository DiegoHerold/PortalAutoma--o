from __future__ import annotations

import os
import zipfile
import io
import json

from tools.certification.packaging import build_package_zip
from tools.certification.manifests import CERTIFICATION_PACKAGES, build_raw_manifest

CERTIFICATION_ROOT = os.environ.get(
    "CERTIFICATION_PACKAGES_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "automation-agent", "certification"),
)


def _source_dir(name: str) -> str:
    return os.path.join(CERTIFICATION_ROOT, name)


def _build(name: str, version: str = "1.0.0"):
    spec = next(s for s in CERTIFICATION_PACKAGES if s.package_id == f"certification.{name}")
    if version != spec.version:
        from dataclasses import replace

        spec = replace(spec, version=version)
    return build_package_zip(
        _source_dir(name),
        f"certification.{name}-{version}.zip",
        automation_yaml=build_raw_manifest(spec),
        manifest_version=version,
    )


def test_build_is_deterministic() -> None:
    first = _build("echo")
    second = _build("echo")
    assert first.sha256 == second.sha256
    assert first.size_bytes == second.size_bytes


def test_build_excludes_pycache_and_contains_portal_and_agent_manifests() -> None:
    built = _build("echo")
    names = zipfile.ZipFile(io.BytesIO(built.zip_bytes)).namelist()
    assert "automation.yaml" in names
    assert "automation.json" in names
    assert "automation/main.py" in names
    assert not any("__pycache__" in n for n in names)
    assert not any(n.endswith((".pyc", ".pyo")) for n in names)


def test_build_updates_agent_manifest_version_for_retry_patch_version() -> None:
    built = _build("echo", version="1.0.1")
    with zipfile.ZipFile(io.BytesIO(built.zip_bytes)) as archive:
        agent_manifest = json.loads(archive.read("automation.json"))
        portal_manifest = archive.read("automation.yaml").decode("utf-8")

    assert agent_manifest["version"] == "1.0.1"
    assert "version: 1.0.1" in portal_manifest


def test_all_packages_build() -> None:
    for name in ("echo", "fail", "timeout", "cancel", "progress", "artifact"):
        built = _build(name)
        assert built.size_bytes > 0
        assert len(built.sha256) == 64
