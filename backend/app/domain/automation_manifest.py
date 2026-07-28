"""
Validation for `automation-workspace.yaml` and `automation.yaml`, matching the
contract documented in docs/automation-catalog.md.

Nothing here ever executes or imports the automation's own code — entrypoint
existence is checked by parsing the target .py file with `ast` (static check
only), never by importing it. This module has zero DB/network dependencies so
it can be unit tested directly (see backend/tests/domain/test_automation_manifest.py).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

DEFAULT_IGNORED_PATHS = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "tests",
    "templates",
    "dist",
    "build",
]

DEFAULT_MANIFEST_FILENAME = "automation.yaml"


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add(self, message: str) -> None:
        self.errors.append(message)


@dataclass
class WorkspaceManifest:
    schema_version: int
    name: str
    automation_roots: list[str]
    manifest_filename: str
    discovery_recursive: bool
    ignored_paths: list[str]


@dataclass
class AutomationManifest:
    schema_version: int
    id: str
    name: str
    version: str
    description: str | None
    category: str | None
    runtime_id: str
    runtime_version: str | None
    entrypoint_type: str
    entrypoint: dict
    interactive_session: bool
    timeout_seconds: int
    required_capabilities: list[str]
    inputs: dict
    raw: dict


def _require_str(data: dict, key: str, result: ValidationResult, path: str = "") -> str | None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        result.add(f"Campo obrigatório ausente ou inválido: {path}{key}")
        return None
    return value


def parse_workspace_manifest(raw_yaml: str) -> tuple[WorkspaceManifest | None, ValidationResult]:
    result = ValidationResult()
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        result.add(f"YAML inválido em automation-workspace.yaml: {exc}")
        return None, result

    if not isinstance(data, dict):
        result.add("automation-workspace.yaml deve ser um mapeamento (objeto) YAML.")
        return None, result

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        result.add("schema_version é obrigatório e deve ser um inteiro.")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        result.add("name é obrigatório em automation-workspace.yaml.")

    automation_roots = data.get("automation_roots")
    if not isinstance(automation_roots, list) or not automation_roots or not all(
        isinstance(r, str) for r in automation_roots
    ):
        result.add("automation_roots é obrigatório e deve ser uma lista não vazia de strings.")
        automation_roots = automation_roots if isinstance(automation_roots, list) else []

    manifest_filename = data.get("manifest_filename", DEFAULT_MANIFEST_FILENAME)
    if not isinstance(manifest_filename, str) or not manifest_filename.strip():
        result.add("manifest_filename deve ser uma string.")
        manifest_filename = DEFAULT_MANIFEST_FILENAME

    discovery = data.get("discovery") or {}
    if not isinstance(discovery, dict):
        result.add("discovery deve ser um mapeamento.")
        discovery = {}
    recursive = discovery.get("recursive", True)
    if not isinstance(recursive, bool):
        result.add("discovery.recursive deve ser booleano.")
        recursive = True
    ignored_paths = discovery.get("ignored_paths", DEFAULT_IGNORED_PATHS)
    if not isinstance(ignored_paths, list) or not all(isinstance(p, str) for p in ignored_paths):
        result.add("discovery.ignored_paths deve ser uma lista de strings.")
        ignored_paths = DEFAULT_IGNORED_PATHS

    if not result.is_valid:
        return None, result

    return (
        WorkspaceManifest(
            schema_version=schema_version,
            name=name,
            automation_roots=automation_roots,
            manifest_filename=manifest_filename,
            discovery_recursive=recursive,
            ignored_paths=ignored_paths,
        ),
        result,
    )


_VALID_ENTRYPOINT_TYPES = {"python-function"}


def parse_automation_manifest(raw_yaml: str) -> tuple[AutomationManifest | None, ValidationResult]:
    result = ValidationResult()
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        result.add(f"YAML inválido em automation.yaml: {exc}")
        return None, result

    if not isinstance(data, dict):
        result.add("automation.yaml deve ser um mapeamento (objeto) YAML.")
        return None, result

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        result.add("schema_version é obrigatório e deve ser um inteiro.")
        schema_version = 0

    automation_id = _require_str(data, "id", result)
    name = _require_str(data, "name", result)
    version = _require_str(data, "version", result)
    description = data.get("description")
    category = data.get("category")

    runtime = data.get("runtime")
    runtime_id: str | None = None
    runtime_version: str | None = None
    if not isinstance(runtime, dict):
        result.add("runtime é obrigatório e deve ser um mapeamento com pelo menos `id`.")
    else:
        runtime_id = _require_str(runtime, "id", result, path="runtime.")
        runtime_version_raw = runtime.get("version")
        runtime_version = str(runtime_version_raw) if runtime_version_raw is not None else None

    entrypoint = data.get("entrypoint")
    entrypoint_type: str | None = None
    if not isinstance(entrypoint, dict):
        result.add("entrypoint é obrigatório e deve ser um mapeamento.")
        entrypoint = {}
    else:
        entrypoint_type = _require_str(entrypoint, "type", result, path="entrypoint.")
        if entrypoint_type and entrypoint_type not in _VALID_ENTRYPOINT_TYPES:
            result.add(
                f"entrypoint.type '{entrypoint_type}' não suportado. Tipos válidos: {sorted(_VALID_ENTRYPOINT_TYPES)}"
            )
        if entrypoint_type == "python-function":
            _require_str(entrypoint, "module", result, path="entrypoint.")
            _require_str(entrypoint, "callable", result, path="entrypoint.")

    execution = data.get("execution") or {}
    if not isinstance(execution, dict):
        result.add("execution deve ser um mapeamento.")
        execution = {}
    interactive_session = execution.get("interactive_session", False)
    if not isinstance(interactive_session, bool):
        result.add("execution.interactive_session deve ser booleano.")
        interactive_session = False
    timeout_seconds = execution.get("timeout_seconds", 300)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        result.add("execution.timeout_seconds deve ser um inteiro positivo.")
        timeout_seconds = 300

    capabilities = data.get("capabilities") or {}
    required_capabilities: list[str] = []
    if capabilities:
        if not isinstance(capabilities, dict):
            result.add("capabilities deve ser um mapeamento.")
        else:
            required = capabilities.get("required", [])
            if not isinstance(required, list) or not all(isinstance(c, str) for c in required):
                result.add("capabilities.required deve ser uma lista de strings.")
            else:
                required_capabilities = required

    inputs = data.get("inputs") or {}
    if inputs and not isinstance(inputs, dict):
        result.add("inputs deve ser um mapeamento de nome -> definição de campo.")
        inputs = {}
    else:
        for field_name, field_def in inputs.items():
            if not isinstance(field_def, dict) or "type" not in field_def:
                result.add(f"inputs.{field_name} deve declarar ao menos `type`.")

    if not result.is_valid:
        return None, result

    return (
        AutomationManifest(
            schema_version=schema_version,
            id=automation_id or "",
            name=name or "",
            version=version or "",
            description=description if isinstance(description, str) else None,
            category=category if isinstance(category, str) else None,
            runtime_id=runtime_id or "",
            runtime_version=runtime_version,
            entrypoint_type=entrypoint_type or "",
            entrypoint=entrypoint,
            interactive_session=interactive_session,
            timeout_seconds=timeout_seconds,
            required_capabilities=required_capabilities,
            inputs=inputs,
            raw=data,
        ),
        result,
    )


def is_path_ignored(relative_path: str, ignored_paths: list[str]) -> bool:
    """True if any segment of relative_path matches an ignored path/glob segment."""
    parts = PurePosixPath(relative_path).parts
    return any(part in ignored_paths for part in parts)


def discover_manifest_paths(
    all_paths: list[str], workspace: WorkspaceManifest
) -> list[str]:
    """
    Given every file path in a repository (POSIX-style, relative to repo root),
    return the subset that are automation manifests under the configured roots,
    respecting `ignored_paths`. Mirrors `automations/**/automation.yaml`.
    """
    matches: list[str] = []
    for raw_path in all_paths:
        path = PurePosixPath(raw_path)
        if path.name != workspace.manifest_filename:
            continue
        if is_path_ignored(raw_path, workspace.ignored_paths):
            continue
        if not any(
            raw_path == root or raw_path.startswith(f"{root.rstrip('/')}/") for root in workspace.automation_roots
        ):
            continue
        matches.append(raw_path)
    return sorted(matches)


def locate_single_manifest(all_paths: list[str], manifest_filename: str = DEFAULT_MANIFEST_FILENAME) -> str | None:
    """
    For a manual ZIP upload: find automation.yaml either at the archive root or
    inside a single top-level folder (the common "one root folder" ZIP shape).
    Returns the relative path to the manifest, or None if not found/ambiguous.
    """
    direct = [p for p in all_paths if p == manifest_filename]
    if direct:
        return direct[0]

    nested = [p for p in all_paths if PurePosixPath(p).name == manifest_filename]
    # Prefer the shallowest match.
    nested.sort(key=lambda p: len(PurePosixPath(p).parts))
    return nested[0] if nested else None


def _module_to_relative_path(module: str) -> tuple[Path, Path]:
    """Given `pkg.sub.main`, return (module file path, package __init__ path)."""
    parts = module.split(".")
    module_file = Path(*parts[:-1], f"{parts[-1]}.py") if len(parts) > 1 else Path(f"{parts[0]}.py")
    init_file = Path(*parts, "__init__.py")
    return module_file, init_file


def validate_entrypoint_on_disk(manifest: AutomationManifest, source_root: Path) -> list[str]:
    """
    Static, non-executing check that the declared entrypoint plausibly exists:
    the module file is present under src/, and (best-effort) a function with the
    declared name is defined at module level, found via `ast.parse` — the code
    is never imported or run.
    """
    errors: list[str] = []
    if manifest.entrypoint_type != "python-function":
        return errors

    module = manifest.entrypoint.get("module", "")
    callable_name = manifest.entrypoint.get("callable", "")
    if not module or not callable_name:
        return errors  # already reported by parse_automation_manifest

    src_dir = source_root / "src"
    if not src_dir.is_dir():
        errors.append(f"Pasta 'src/' não encontrada em {source_root}.")
        return errors

    module_file, _init_file = _module_to_relative_path(module)
    candidate = src_dir / module_file
    if not candidate.is_file():
        errors.append(f"Módulo declarado em entrypoint.module não encontrado: src/{module_file.as_posix()}")
        return errors

    try:
        tree = ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))
    except (SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f"Não foi possível analisar {candidate.name} estaticamente: {exc}")
        return errors

    found = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    # Restrict to module-level definitions (direct children of the module body)
    # to avoid false positives from nested helper functions with the same name.
    top_level = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
        for node in tree.body
    )
    if not top_level and not found:
        errors.append(
            f"Callable '{callable_name}' declarado em entrypoint não encontrado em src/{module_file.as_posix()}."
        )
    return errors
