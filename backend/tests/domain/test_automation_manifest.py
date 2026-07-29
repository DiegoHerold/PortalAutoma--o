from pathlib import Path

import pytest

from modules.catalog.domain.manifest import (
    discover_manifest_paths,
    locate_single_manifest,
    parse_automation_manifest,
    parse_workspace_manifest,
    validate_entrypoint_on_disk,
)

WORKSPACE_YAML = """
schema_version: 1
name: Biason Automations
automation_roots:
  - automations
manifest_filename: automation.yaml
discovery:
  recursive: true
  ignored_paths:
    - .git
    - .venv
    - venv
    - __pycache__
    - tests
    - templates
    - dist
    - build
"""

AUTOMATION_YAML = """
schema_version: 1
id: dominio.atualizar
name: Atualizar Domínio Contábil
version: 1.0.0
description: Atualiza o sistema Domínio Contábil.
category: dominio
runtime:
  id: python-desktop
  version: 1
entrypoint:
  type: python-function
  module: atualizar_dominio.main
  callable: run
execution:
  interactive_session: true
  timeout_seconds: 7200
capabilities:
  required:
    - desktop.winauto
    - software.dominio
inputs:
  versao:
    type: string
    title: Versão
    required: false
"""


def test_parse_workspace_manifest_valid():
    ws, result = parse_workspace_manifest(WORKSPACE_YAML)
    assert result.is_valid, result.errors
    assert ws.automation_roots == ["automations"]
    assert ws.manifest_filename == "automation.yaml"
    assert ws.discovery_recursive is True
    assert ".git" in ws.ignored_paths


def test_parse_workspace_manifest_missing_roots():
    _, result = parse_workspace_manifest("schema_version: 1\nname: X\n")
    assert not result.is_valid
    assert any("automation_roots" in e for e in result.errors)


def test_parse_workspace_manifest_invalid_yaml():
    _, result = parse_workspace_manifest("not: [valid: yaml")
    assert not result.is_valid


def test_discover_manifest_paths_respects_roots_and_ignored():
    ws, _ = parse_workspace_manifest(WORKSPACE_YAML)
    all_paths = [
        "automation-workspace.yaml",
        "automations/dominio/atualizar-dominio/automation.yaml",
        "automations/dominio/atualizar-dominio/tests/automation.yaml",  # ignored (tests/)
        "automations/gestta/baixar-documentos/automation.yaml",
        "automations/gestta/baixar-documentos/.venv/lib/automation.yaml",  # ignored (.venv/)
        "templates/base-template/automation.yaml",  # outside automation_roots
        "README.md",
    ]
    found = discover_manifest_paths(all_paths, ws)
    assert found == [
        "automations/dominio/atualizar-dominio/automation.yaml",
        "automations/gestta/baixar-documentos/automation.yaml",
    ]


def test_discover_manifest_paths_duplicate_ids_are_caller_responsibility():
    # discover_manifest_paths only locates files; duplicate-id detection happens
    # one layer up (discovery service) after parsing each manifest's `id`.
    ws, _ = parse_workspace_manifest(WORKSPACE_YAML)
    all_paths = [
        "automations/a/automation.yaml",
        "automations/b/automation.yaml",
    ]
    assert len(discover_manifest_paths(all_paths, ws)) == 2


def test_parse_automation_manifest_valid():
    manifest, result = parse_automation_manifest(AUTOMATION_YAML)
    assert result.is_valid, result.errors
    assert manifest.id == "dominio.atualizar"
    assert manifest.version == "1.0.0"
    assert manifest.entrypoint_type == "python-function"
    assert manifest.entrypoint["module"] == "atualizar_dominio.main"
    assert [capability.key for capability in manifest.required_capabilities] == ["desktop.winauto", "software.dominio"]
    assert manifest.interactive_session is True
    assert manifest.timeout_seconds == 7200


@pytest.mark.parametrize(
    "broken_field,replacement",
    [
        ("id: dominio.atualizar\n", ""),
        ("version: 1.0.0\n", ""),
        ("  callable: run\n", ""),
        ("  module: atualizar_dominio.main\n", ""),
    ],
)
def test_parse_automation_manifest_rejects_missing_required_fields(broken_field, replacement):
    broken_yaml = AUTOMATION_YAML.replace(broken_field, replacement)
    manifest, result = parse_automation_manifest(broken_yaml)
    assert manifest is None
    assert not result.is_valid


def test_parse_automation_manifest_rejects_unknown_entrypoint_type():
    broken = AUTOMATION_YAML.replace("type: python-function", "type: shell-script")
    manifest, result = parse_automation_manifest(broken)
    assert manifest is None
    assert any("Unsupported entrypoint type" in e for e in result.errors)


def test_locate_single_manifest_at_root():
    assert locate_single_manifest(["automation.yaml", "src/x.py"]) == "automation.yaml"


def test_locate_single_manifest_inside_single_folder():
    paths = ["atualizar-dominio/automation.yaml", "atualizar-dominio/src/atualizar_dominio/main.py"]
    assert locate_single_manifest(paths) == "atualizar-dominio/automation.yaml"


def test_locate_single_manifest_returns_none_when_absent():
    assert locate_single_manifest(["src/x.py", "README.md"]) is None


def test_validate_entrypoint_on_disk_ok(tmp_path: Path):
    manifest, _ = parse_automation_manifest(AUTOMATION_YAML)
    pkg_dir = tmp_path / "src" / "atualizar_dominio"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "main.py").write_text("async def run(context):\n    return {}\n", encoding="utf-8")
    errors = validate_entrypoint_on_disk(manifest, tmp_path)
    assert errors == []


def test_validate_entrypoint_on_disk_missing_module(tmp_path: Path):
    manifest, _ = parse_automation_manifest(AUTOMATION_YAML)
    (tmp_path / "src").mkdir()
    errors = validate_entrypoint_on_disk(manifest, tmp_path)
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_validate_entrypoint_on_disk_missing_callable(tmp_path: Path):
    manifest, _ = parse_automation_manifest(AUTOMATION_YAML)
    pkg_dir = tmp_path / "src" / "atualizar_dominio"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "main.py").write_text("async def other(context):\n    return {}\n", encoding="utf-8")
    errors = validate_entrypoint_on_disk(manifest, tmp_path)
    assert len(errors) == 1
    assert "run" in errors[0]


def test_validate_entrypoint_never_imports_the_module(tmp_path: Path, monkeypatch):
    """Guard against regressions that would import/exec the automation code."""
    manifest, _ = parse_automation_manifest(AUTOMATION_YAML)
    pkg_dir = tmp_path / "src" / "atualizar_dominio"
    pkg_dir.mkdir(parents=True)
    # If this file were imported, it would raise at import time.
    (pkg_dir / "main.py").write_text(
        "raise RuntimeError('should never be imported during validation')\n"
        "async def run(context):\n    return {}\n",
        encoding="utf-8",
    )
    errors = validate_entrypoint_on_disk(manifest, tmp_path)
    assert errors == []
