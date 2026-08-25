from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from modules.catalog.domain.automation_version import AutomationVersion
from modules.catalog.domain.errors import InvalidCatalogStateTransition
from modules.catalog.domain.manifest import parse_automation_manifest, validate_manifest_package_paths
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


def test_manifest_parser_accepts_browser_playwright_entrypoint() -> None:
    # Regressao: o Portal recusava publicar qualquer automacao
    # browser_playwright porque "browser-playwright" nao estava em
    # SUPPORTED_ENTRYPOINT_TYPES, mesmo o Agent ja suportando esse tipo de
    # entrypoint (ManifestValidator.cs / BrowserPlaywrightLauncher.cs).
    manifest_json = json.dumps(
        {
            "schema_version": "1.0",
            "automation": {
                "id": "dominio.demo_browser",
                "name": "Demo navegador",
                "version": "1.0.0",
            },
            "entrypoint": {"type": "browser-playwright", "module": "automation.main", "function": "run"},
            "runtime": {"id": "python-browser", "version": "3.13-playwright"},
            "execution": {"mode": "background", "timeout_seconds": 300},
            "resources": {"cpu_units": 1, "memory_mb": 1536, "disk_mb": 200},
            "capabilities": {"required": [{"key": "agent.browser_execution"}]},
        }
    )

    manifest, result = parse_automation_manifest(manifest_json)

    assert result.is_valid, result.errors
    assert manifest is not None
    assert manifest.entrypoint_type == "browser-playwright"


def test_manifest_package_paths_accept_root_relative_python_function_entrypoint() -> None:
    # Regressao: validate_manifest_package_paths so aceitava
    # "application/<modulo>.py" (prefixo fixo), mas o Agent
    # (RuntimeLauncher.BuildPythonFunction/PythonFunctionLauncher.cs) faz
    # sys.path.insert(0, package_root) e importa o modulo direto - ou seja,
    # o layout real e correto e "<modulo>.py" na RAIZ do pacote (ex.:
    # "automation.main" -> "automation/main.py"). Isso rejeitava com
    # MANIFEST_ENTRYPOINT_NOT_FOUND todo pacote python-function
    # corretamente estruturado que nao declarasse um "path" explicito.
    manifest, result = parse_automation_manifest(
        json.dumps(
            {
                "schema_version": "1.0",
                "automation": {"id": "dominio.demo_root_layout", "name": "Demo", "version": "1.0.0"},
                "entrypoint": {"type": "python-function", "module": "automation.main", "function": "run"},
                "runtime": {"id": "python-core", "version": "3.13"},
            }
        )
    )
    assert result.is_valid, result.errors
    assert manifest is not None

    package_result = validate_manifest_package_paths(manifest, {"automation.yaml", "automation/main.py"})
    assert package_result.is_valid, package_result.errors


def test_zip_validator_allows_extensions_required_by_declared_entrypoint_type() -> None:
    # Regressao: FORBIDDEN_EXTENSIONS bloqueava .ps1/.exe incondicionalmente
    # para QUALQUER pacote, entao nenhum pacote powershell_script/executable
    # jamais passava na validacao de upload - mesmo sendo tipos suportados e
    # documentados do proprio Agent. A extensao so e liberada quando o
    # entrypoint.type declarado no manifesto realmente precisa dela.
    powershell_manifest = json.dumps(
        {
            "schema_version": 1,
            "id": "dominio.demo_powershell",
            "name": "Demo PowerShell",
            "version": "1.0.0",
            "runtime": {"id": "powershell", "version": "system"},
            "entrypoint": {"type": "powershell-script", "script": "automation/main.ps1"},
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "ps.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("automation.yaml", powershell_manifest)
            archive.writestr("automation/main.ps1", "Write-Output 'ok'")

        result = ZipPackageValidator().validate_zip_package(zip_path, max_size_bytes=1024 * 1024)

    assert result["valid"], result["issues"]


def test_zip_validator_still_blocks_unexpected_executable_for_other_entrypoint_types() -> None:
    # A excecao acima e por tipo de entrypoint declarado, nao um bypass
    # geral: um pacote python-function com um .exe extra continua
    # bloqueado - a postura de seguranca original se mantem pros tipos que
    # nao precisam de binario nenhum.
    python_manifest = json.dumps(
        {
            "schema_version": 1,
            "id": "dominio.demo_python",
            "name": "Demo Python",
            "version": "1.0.0",
            "runtime": {"id": "python-core", "version": "3.13"},
            "entrypoint": {"type": "python-function", "module": "automation.main", "function": "run"},
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "py.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("automation.yaml", python_manifest)
            archive.writestr("automation/main.py", "def run(ctx):\n    return {}\n")
            archive.writestr("automation/suspicious.exe", b"MZ\x00\x00")

        result = ZipPackageValidator().validate_zip_package(zip_path, max_size_bytes=1024 * 1024)

    assert not result["valid"]
    assert any(issue["code"] == "PACKAGE_FORBIDDEN_EXTENSION" for issue in result["issues"])


def test_zip_validator_blocks_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("automation.yaml", "schema_version: 1")
            archive.writestr("../escape.txt", "bad")

        result = ZipPackageValidator().validate_zip_package(zip_path, max_size_bytes=1024 * 1024)

    assert not result["valid"]
    assert any(issue["code"] == "PACKAGE_UNSAFE_PATH" for issue in result["issues"])
