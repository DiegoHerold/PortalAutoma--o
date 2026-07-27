from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from modules.catalog.domain.automation_version import AutomationVersion
from modules.catalog.domain.errors import InvalidCatalogStateTransition
from modules.catalog.domain.manifest import parse_automation_manifest
from modules.catalog.domain.states import AutomationVersionStatus
from modules.catalog.domain.value_objects import AutomationKey, SemVer
from modules.catalog.infrastructure.package_validation import ZipPackageValidator


def test_automation_key_and_semver_are_validated() -> None:
    AutomationKey("dominio.importar_documentos")
    SemVer("1.2.0")
    for factory, value in [(AutomationKey, "Dominio"), (SemVer, "1")]:
        try:
            factory(value)
        except ValueError:
            continue
        raise AssertionError(f"{factory.__name__} accepted invalid value {value}")


def test_automation_version_state_machine_blocks_invalid_transition() -> None:
    version = AutomationVersion(
        id="v1",
        automation_id="a1",
        version="1.0.0",
        status=AutomationVersionStatus.PUBLISHED,
        manifest_id="m1",
        package_id="p1",
        runtime_version_id="r1",
    )
    try:
        version.transition_to(AutomationVersionStatus.DRAFT)
    except InvalidCatalogStateTransition:
        return
    raise AssertionError("published -> draft transition should be invalid")


def test_manifest_parser_accepts_new_contract_shape() -> None:
    manifest_json = json.dumps(
        {
            "schema_version": "1.0",
            "automation": {
                "id": "dominio.importar_documentos",
                "name": "Importar documentos",
                "version": "1.2.0",
            },
            "entrypoint": {"type": "python-function", "module": "automation.main", "function": "run"},
            "runtime": {"id": "python-desktop", "version": "1.0.0"},
            "execution": {"mode": "interactive", "timeout_seconds": 3600},
            "resources": {"cpu_units": 1, "memory_mb": 1024, "disk_mb": 500},
            "capabilities": {"required": [{"key": "os.windows", "version": ">=10"}]},
            "schemas": {"input": "schemas/input.schema.json"},
        }
    )

    manifest, result = parse_automation_manifest(manifest_json)

    assert result.is_valid, result.errors
    assert manifest is not None
    assert manifest.id == "dominio.importar_documentos"
    assert manifest.entrypoint["function"] == "run"
    assert manifest.required_capabilities[0].key == "os.windows"


def test_zip_validator_blocks_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("automation.yaml", "schema_version: 1")
            archive.writestr("../escape.txt", "bad")

        result = ZipPackageValidator().validate_zip_package(zip_path, max_size_bytes=1024 * 1024)

    assert not result["valid"]
    assert any(issue["code"] == "PACKAGE_UNSAFE_PATH" for issue in result["issues"])
