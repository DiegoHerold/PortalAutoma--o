"""These tests do not require a database or the running Portal — they only
exercise the pure YAML-building logic in tools.certification.manifests
against the grammar documented in modules/catalog/domain/manifest.py.

For a full round-trip through the real parser (parse_automation_manifest),
run this suite inside the backend container on Python >= 3.11 — see
docs/certification-harness.md, "Testes do Harness".
"""

from __future__ import annotations

import yaml

from tools.certification.manifests import (
    CERTIFICATION_PACKAGES,
    CERTIFICATION_RUNTIME_ID,
    CERTIFICATION_RUNTIME_VERSION,
    build_raw_manifest,
)


def test_six_certification_packages_defined() -> None:
    ids = {spec.package_id for spec in CERTIFICATION_PACKAGES}
    assert ids == {
        "certification.echo",
        "certification.fail",
        "certification.timeout",
        "certification.cancel",
        "certification.progress",
        "certification.artifact",
    }


def test_manifest_yaml_matches_catalog_grammar() -> None:
    # Mirrors the required-field checks in
    # modules/catalog/domain/manifest.py::parse_automation_manifest without
    # importing it directly (that module requires Python >= 3.11 for
    # enum.StrEnum, which this dev sandbox does not have).
    for spec in CERTIFICATION_PACKAGES:
        text = build_raw_manifest(spec)
        data = yaml.safe_load(text)

        assert data["schema_version"] in (1, "1", "1.0")
        assert data["id"] == spec.package_id
        assert data["name"]
        assert data["version"] == spec.version

        assert isinstance(data["runtime"], dict)
        assert data["runtime"]["id"] == CERTIFICATION_RUNTIME_ID
        assert data["runtime"]["version"] == CERTIFICATION_RUNTIME_VERSION

        entrypoint = data["entrypoint"]
        assert entrypoint["type"] == "python-function"  # hyphenated: Portal Catalog grammar
        assert entrypoint["module"] == spec.module
        assert entrypoint["function"] == spec.callable_name
        assert entrypoint["path"] == "automation/main.py"

        execution = data["execution"]
        assert execution["mode"] == "background"
        assert execution["timeout_seconds"] == spec.timeout_seconds
        assert execution["graceful_cancellation_seconds"] == spec.graceful_cancellation_seconds

        resources = data["resources"]
        for key in ("cpu_units", "memory_mb", "disk_mb"):
            assert isinstance(resources[key], int) and resources[key] > 0

        capabilities = data["capabilities"]["required"]
        assert "windows" in capabilities
        assert "agent.background_execution" in capabilities


def test_timeout_scenario_has_short_execution_window() -> None:
    spec = next(s for s in CERTIFICATION_PACKAGES if s.package_id == "certification.timeout")
    assert spec.timeout_seconds < 30, "certification.timeout must time out quickly to keep the suite fast"
