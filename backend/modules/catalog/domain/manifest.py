from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from modules.catalog.domain.value_objects import AutomationKey, SemVer
from modules.fleet.domain.capability import CapabilityRequirement

DEFAULT_MANIFEST_FILENAME = "automation.yaml"
SUPPORTED_SCHEMA_VERSIONS = {"1", "1.0"}
SUPPORTED_ENTRYPOINT_TYPES = {
    "python-function",
    "python-module",
    "powershell-script",
    "executable",
    "browser-playwright",
    # Automação externa (ADR-018, modo direto): já instalada na máquina dela, fala com o
    # Portal pelo SDK. Não tem pacote para o Agent baixar nem runtime fornecido pelo Portal.
    "externa",
}
ENTRYPOINT_EXTERNA = "externa"
SUPPORTED_EXECUTION_MODES = {"interactive", "background", "browser"}
# Modo de execução (decisão 10): obrigatório. Nomes em português ou os do pool.
EXECUTION_MODE_ALIASES = {
    "tela": "interactive",
    "navegador": "browser",
    "segundo_plano": "background",
    "interactive": "interactive",
    "browser": "browser",
    "background": "background",
}
EXECUTION_MODE_LABELS = {"interactive": "tela", "browser": "navegador", "background": "segundo_plano"}
STEP_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
ATTRIBUTE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,60}$")


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


@dataclass(frozen=True)
class WorkspaceManifest:
    schema_version: int
    name: str
    automation_roots: list[str]
    manifest_filename: str
    discovery_recursive: bool
    ignored_paths: list[str]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [f"{issue.path}: {issue.message}" if issue.path else issue.message for issue in self.issues]

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def add(self, code: str, path: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.issues.append(ValidationIssue(code=code, path=path, message=message, details=details or {}))

    def to_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "code": issue.code,
                "path": issue.path,
                "message": issue.message,
                "details": issue.details,
            }
            for issue in self.issues
        ]


@dataclass(frozen=True)
class Entrypoint:
    type: str
    module: str | None = None
    function: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class ExecutionSpec:
    mode: str
    timeout_seconds: int
    graceful_cancellation_seconds: int
    # Repetir sozinha depois de falha. Automação de tela só repete se declarar que é seguro.
    safe_to_retry: bool = False
    # Estado guardado fora da máquina: "continuar de onde parou" pode ir para outra máquina.
    central_state: bool = False


@dataclass(frozen=True)
class ItemSpec:
    """O que é um item desta automação (Empresa, Nota, Cliente)."""

    label: str
    key: str
    label_attribute: str | None = None
    group_attribute: str | None = None
    attributes_schema: dict[str, Any] | None = None
    work_attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepSpec:
    """Etapa declarada, na ordem em que roda."""

    key: str
    name: str
    per_item: bool = True
    per_task: bool = False


@dataclass(frozen=True)
class ResourceRequirements:
    cpu_units: int
    memory_mb: int
    disk_mb: int


@dataclass(frozen=True)
class SchemaReferences:
    input: str | None = None
    output: str | None = None


@dataclass(frozen=True)
class AutomationManifest:
    schema_version: str
    id: str
    name: str
    version: str
    description: str | None
    category: str | None
    runtime_id: str
    runtime_version: str | None
    entrypoint_type: str
    entrypoint: dict[str, Any]
    execution: ExecutionSpec
    resources: ResourceRequirements
    required_capabilities: tuple[CapabilityRequirement, ...]
    exclusive_resources: tuple[str, ...]
    schemas: SchemaReferences
    raw: dict[str, Any]
    normalized: dict[str, Any]
    content_hash: str
    items: ItemSpec | None = None
    steps: tuple[StepSpec, ...] = ()

    @property
    def timeout_seconds(self) -> int:
        return self.execution.timeout_seconds

    @property
    def interactive_session(self) -> bool:
        return self.execution.mode == "interactive"


def parse_automation_manifest(raw_yaml: str) -> tuple[AutomationManifest | None, ValidationResult]:
    result = ValidationResult()
    data, parse_error = _load_manifest_mapping(raw_yaml)
    if parse_error:
        result.add("MANIFEST_PARSE_ERROR", "", parse_error)
        return None, result

    if not isinstance(data, dict):
        result.add("MANIFEST_NOT_MAPPING", "", "automation.yaml must be a mapping.")
        return None, result

    schema_version = _normalize_schema_version(data.get("schema_version"), result)
    automation_block = data.get("automation") if isinstance(data.get("automation"), dict) else data
    automation_id = _required_string(automation_block, "id", result, "automation.id" if "automation" in data else "id")
    name = _required_string(automation_block, "name", result, "automation.name" if "automation" in data else "name")
    version = _required_string(
        automation_block,
        "version",
        result,
        "automation.version" if "automation" in data else "version",
    )
    description = _optional_string(automation_block, "description")
    category = _optional_string(automation_block, "category") or _optional_string(data, "category")

    if automation_id:
        try:
            AutomationKey(automation_id)
        except ValueError as exc:
            result.add("MANIFEST_INVALID_AUTOMATION_KEY", "automation.id", str(exc), {"value": automation_id})
    if version:
        try:
            SemVer(version)
        except ValueError as exc:
            result.add("MANIFEST_INVALID_VERSION", "automation.version", str(exc), {"value": version})

    runtime = data.get("runtime")
    runtime_id = ""
    runtime_version = None
    if not isinstance(runtime, dict):
        result.add("MANIFEST_RUNTIME_REQUIRED", "runtime", "runtime is required and must be a mapping.")
    else:
        runtime_id = _required_string(runtime, "id", result, "runtime.id") or ""
        runtime_version = _optional_string(runtime, "version")

    entrypoint = _parse_entrypoint(data.get("entrypoint"), result)
    execution = _parse_execution(data.get("execution"), result)
    resources = _parse_resources(data.get("resources"), result)
    required_capabilities = _parse_capability_requirements(data.get("capabilities"), result)
    exclusive_resources = _parse_string_list(data.get("exclusive_resources"), "exclusive_resources", result)
    schemas = _parse_schema_refs(data.get("schemas"), result)
    items = _parse_items(data.get("itens"), result)
    steps = _parse_steps(data.get("etapas"), result)
    parameters = _parse_parameters(data.get("parametros", data.get("parameters")), result)

    if not result.is_valid:
        return None, result

    normalized = {
        "schema_version": schema_version,
        "automation": {
            "id": automation_id,
            "name": name,
            "version": version,
            "description": description,
            "category": category,
        },
        "runtime": {
            "id": runtime_id,
            "version": runtime_version,
        },
        "entrypoint": entrypoint,
        "parameters": parameters,
        "execution": {
            "mode": execution.mode,
            "timeout_seconds": execution.timeout_seconds,
            "graceful_cancellation_seconds": execution.graceful_cancellation_seconds,
            "safe_to_retry": execution.safe_to_retry,
            "central_state": execution.central_state,
        },
        "items": None if items is None else {
            "label": items.label,
            "key": items.key,
            "label_attribute": items.label_attribute,
            "group_attribute": items.group_attribute,
            "attributes_schema": items.attributes_schema,
            "work_attributes": list(items.work_attributes),
        },
        "steps": [
            {"key": s.key, "name": s.name, "per_item": s.per_item, "per_task": s.per_task} for s in steps
        ],
        "resources": {
            "cpu_units": resources.cpu_units,
            "memory_mb": resources.memory_mb,
            "disk_mb": resources.disk_mb,
        },
        "capabilities": {
            "required": [
                {
                    "key": capability.key,
                    "version": capability.version,
                    "attributes": capability.attributes,
                }
                for capability in required_capabilities
            ],
        },
        "exclusive_resources": list(exclusive_resources),
        "schemas": {
            "input": schemas.input,
            "output": schemas.output,
        },
    }

    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return (
        AutomationManifest(
            schema_version=schema_version,
            id=automation_id or "",
            name=name or "",
            version=version or "",
            description=description,
            category=category,
            runtime_id=runtime_id,
            runtime_version=runtime_version,
            entrypoint_type=entrypoint["type"],
            entrypoint=entrypoint,
            execution=execution,
            resources=resources,
            required_capabilities=tuple(required_capabilities),
            exclusive_resources=exclusive_resources,
            schemas=schemas,
            raw=data,
            normalized=normalized,
            content_hash=hashlib.sha256(canonical).hexdigest(),
            items=items,
            steps=steps,
        ),
        result,
    )


def parse_workspace_manifest(raw_yaml: str) -> tuple[WorkspaceManifest | None, ValidationResult]:
    result = ValidationResult()
    data, parse_error = _load_manifest_mapping(raw_yaml)
    if parse_error:
        result.add("WORKSPACE_PARSE_ERROR", "", parse_error)
        return None, result
    if not isinstance(data, dict):
        result.add("WORKSPACE_NOT_MAPPING", "", "automation-workspace.yaml must be a mapping.")
        return None, result

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        result.add("WORKSPACE_SCHEMA_VERSION_REQUIRED", "schema_version", "schema_version must be an integer.")
        schema_version = 0

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        result.add("WORKSPACE_NAME_REQUIRED", "name", "name is required.")
        name = ""

    automation_roots = data.get("automation_roots")
    if not isinstance(automation_roots, list) or not automation_roots or not all(isinstance(item, str) and item.strip() for item in automation_roots):
        result.add("WORKSPACE_AUTOMATION_ROOTS_REQUIRED", "automation_roots", "automation_roots must be a non-empty string list.")
        automation_roots = []

    manifest_filename = data.get("manifest_filename", DEFAULT_MANIFEST_FILENAME)
    if not isinstance(manifest_filename, str) or not manifest_filename.strip():
        result.add("WORKSPACE_MANIFEST_FILENAME_INVALID", "manifest_filename", "manifest_filename must be a string.")
        manifest_filename = DEFAULT_MANIFEST_FILENAME

    discovery = data.get("discovery") or {}
    if not isinstance(discovery, dict):
        result.add("WORKSPACE_DISCOVERY_INVALID", "discovery", "discovery must be a mapping.")
        discovery = {}
    recursive = discovery.get("recursive", True)
    if not isinstance(recursive, bool):
        result.add("WORKSPACE_DISCOVERY_RECURSIVE_INVALID", "discovery.recursive", "discovery.recursive must be boolean.")
        recursive = True
    ignored_paths = discovery.get("ignored_paths", DEFAULT_IGNORED_PATHS)
    if not isinstance(ignored_paths, list) or not all(isinstance(item, str) for item in ignored_paths):
        result.add("WORKSPACE_IGNORED_PATHS_INVALID", "discovery.ignored_paths", "ignored_paths must be a string list.")
        ignored_paths = DEFAULT_IGNORED_PATHS

    if not result.is_valid:
        return None, result
    return (
        WorkspaceManifest(
            schema_version=schema_version,
            name=name.strip(),
            automation_roots=[item.strip().rstrip("/") for item in automation_roots],
            manifest_filename=manifest_filename.strip(),
            discovery_recursive=recursive,
            ignored_paths=ignored_paths,
        ),
        result,
    )


def discover_manifest_paths(all_paths: list[str], workspace: WorkspaceManifest) -> list[str]:
    matches: list[str] = []
    for raw_path in all_paths:
        path = PurePosixPath(raw_path)
        if path.name != workspace.manifest_filename:
            continue
        if _is_path_ignored(raw_path, workspace.ignored_paths):
            continue
        if not any(raw_path == root or raw_path.startswith(f"{root.rstrip('/')}/") for root in workspace.automation_roots):
            continue
        matches.append(raw_path)
    return sorted(matches)


def validate_manifest_package_paths(manifest: AutomationManifest, package_paths: set[str]) -> ValidationResult:
    result = ValidationResult()
    for label, value in (("schemas.input", manifest.schemas.input), ("schemas.output", manifest.schemas.output)):
        if value is None:
            continue
        if not _is_safe_relative_path(value):
            result.add("MANIFEST_UNSAFE_SCHEMA_PATH", label, "Schema path must be relative and stay inside the package.")
            continue
        if value not in package_paths:
            result.add("MANIFEST_SCHEMA_NOT_FOUND", label, "Referenced schema does not exist in the package.", {"path": value})

    entrypoint_candidates = _entrypoint_relative_path_candidates(manifest.entrypoint)
    if entrypoint_candidates and not any(candidate in package_paths for candidate in entrypoint_candidates):
        result.add(
            "MANIFEST_ENTRYPOINT_NOT_FOUND",
            "entrypoint",
            "Entrypoint file referenced by the manifest was not found in the package.",
            {"path": entrypoint_candidates[0], "candidates": entrypoint_candidates},
        )
    return result


def validate_entrypoint_on_disk(manifest: AutomationManifest, source_root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.entrypoint_type != "python-function":
        return errors
    module = manifest.entrypoint.get("module")
    function = manifest.entrypoint.get("function") or manifest.entrypoint.get("callable")
    if not module or not function:
        return errors
    candidate = source_root / _module_to_relative_path(module)
    if not candidate.is_file():
        src_candidate = source_root / "src" / _module_to_relative_path(module)
        app_candidate = source_root / "application" / _module_to_relative_path(module)
        candidate = src_candidate if src_candidate.is_file() else app_candidate
    if not candidate.is_file():
        errors.append(f"Entrypoint module not found: {module}")
        return errors
    try:
        tree = ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))
    except (SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f"Entrypoint module cannot be parsed safely: {exc}")
        return errors
    top_level = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function
        for node in tree.body
    )
    if not top_level:
        errors.append(f"Entrypoint function '{function}' not found in {candidate.name}.")
    return errors


def locate_single_manifest(all_paths: list[str], manifest_filename: str = DEFAULT_MANIFEST_FILENAME) -> str | None:
    direct = [p for p in all_paths if p == manifest_filename]
    if direct:
        return direct[0]
    nested = [p for p in all_paths if PurePosixPath(p).name == manifest_filename]
    nested.sort(key=lambda p: len(PurePosixPath(p).parts))
    return nested[0] if nested else None


def _load_manifest_mapping(raw_yaml: str) -> tuple[Any, str | None]:
    try:
        import yaml
    except ModuleNotFoundError:
        try:
            return json.loads(raw_yaml), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid automation manifest YAML and PyYAML is not installed: {exc}"

    try:
        return yaml.safe_load(raw_yaml) or {}, None
    except yaml.YAMLError as exc:
        return None, f"Invalid automation manifest YAML: {exc}"


def _normalize_schema_version(value: Any, result: ValidationResult) -> str:
    if value is None:
        result.add("MANIFEST_SCHEMA_VERSION_REQUIRED", "schema_version", "schema_version is required.")
        return ""
    schema_version = str(value)
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        result.add(
            "MANIFEST_SCHEMA_VERSION_UNSUPPORTED",
            "schema_version",
            "Unsupported manifest schema version.",
            {"supported": sorted(SUPPORTED_SCHEMA_VERSIONS), "value": schema_version},
        )
    return schema_version


def _required_string(data: dict[str, Any], key: str, result: ValidationResult, path: str) -> str | None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        result.add("MANIFEST_REQUIRED_FIELD", path, "Required string field is missing or invalid.")
        return None
    return value.strip()


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_parameters(raw: Any, result: ValidationResult) -> list[dict[str, Any]]:
    """Campos de entrada sugeridos (Fase 7). O Portal pode editá-los depois livremente."""
    if raw in (None, []):
        return []
    from modules.catalog.domain.formulario import FormularioInvalido, validar_campos

    try:
        return [c.publico() for c in validar_campos(raw)]
    except FormularioInvalido as exc:
        for caminho, mensagem in exc.campos.items():
            result.add("MANIFEST_PARAMETER_INVALID", f"parametros.{caminho}", mensagem)
        return []


def _parse_entrypoint(raw_entrypoint: Any, result: ValidationResult) -> dict[str, Any]:
    if not isinstance(raw_entrypoint, dict):
        result.add("MANIFEST_ENTRYPOINT_REQUIRED", "entrypoint", "entrypoint is required and must be a mapping.")
        return {"type": ""}
    entrypoint_type = _required_string(raw_entrypoint, "type", result, "entrypoint.type") or ""
    if entrypoint_type and entrypoint_type not in SUPPORTED_ENTRYPOINT_TYPES:
        result.add(
            "MANIFEST_ENTRYPOINT_TYPE_UNSUPPORTED",
            "entrypoint.type",
            "Unsupported entrypoint type.",
            {"supported": sorted(SUPPORTED_ENTRYPOINT_TYPES), "value": entrypoint_type},
        )
    entrypoint = dict(raw_entrypoint)
    if entrypoint_type == "python-function":
        _required_string(entrypoint, "module", result, "entrypoint.module")
        function = entrypoint.get("function") or entrypoint.get("callable")
        if not isinstance(function, str) or not function.strip():
            result.add("MANIFEST_ENTRYPOINT_FUNCTION_REQUIRED", "entrypoint.function", "function is required.")
        else:
            entrypoint["function"] = function
            entrypoint.setdefault("callable", function)
    if "path" in entrypoint and isinstance(entrypoint["path"], str) and not _is_safe_relative_path(entrypoint["path"]):
        result.add("MANIFEST_ENTRYPOINT_UNSAFE_PATH", "entrypoint.path", "Entrypoint path is unsafe.")
    return entrypoint


def _parse_execution(raw_execution: Any, result: ValidationResult) -> ExecutionSpec:
    execution = raw_execution if isinstance(raw_execution, dict) else {}
    if raw_execution is not None and not isinstance(raw_execution, dict):
        result.add("MANIFEST_EXECUTION_INVALID", "execution", "execution must be a mapping.")
    mode = execution.get("mode")
    if mode is None and execution.get("interactive_session") is True:
        mode = "interactive"  # forma antiga de declarar tela
    if mode is None:
        result.add(
            "MANIFEST_EXECUTION_MODE_REQUIRED",
            "execution.mode",
            "Declare como a automação executa: execution.mode = tela, navegador ou segundo_plano.",
        )
        mode = "background"
    elif mode not in EXECUTION_MODE_ALIASES:
        result.add("MANIFEST_EXECUTION_MODE_UNSUPPORTED", "execution.mode", "Unsupported execution mode.", {"value": mode})
        mode = "background"
    else:
        mode = EXECUTION_MODE_ALIASES[mode]
    safe_to_retry = execution.get("seguro_repetir", execution.get("safe_to_retry", False))
    central_state = execution.get("estado_central", execution.get("central_state", False))
    for name, value in (("seguro_repetir", safe_to_retry), ("estado_central", central_state)):
        if not isinstance(value, bool):
            result.add("MANIFEST_EXECUTION_FLAG_INVALID", f"execution.{name}", f"{name} deve ser true ou false.")
    timeout_seconds = execution.get("timeout_seconds", 300)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        result.add("MANIFEST_EXECUTION_TIMEOUT_INVALID", "execution.timeout_seconds", "Timeout must be a positive integer.")
        timeout_seconds = 300
    graceful = execution.get("graceful_cancellation_seconds", 30)
    if not isinstance(graceful, int) or graceful < 0:
        result.add(
            "MANIFEST_GRACEFUL_CANCELLATION_INVALID",
            "execution.graceful_cancellation_seconds",
            "Graceful cancellation seconds must be a non-negative integer.",
        )
        graceful = 30
    return ExecutionSpec(
        mode=mode,
        timeout_seconds=timeout_seconds,
        graceful_cancellation_seconds=graceful,
        safe_to_retry=safe_to_retry is True,
        central_state=central_state is True,
    )


def _parse_items(raw: Any, result: ValidationResult) -> ItemSpec | None:
    """Bloco ``itens``: opcional (automação sem itens só tem início, fim e log)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        result.add("MANIFEST_ITEMS_INVALID", "itens", "itens deve ser um mapeamento.")
        return None
    label = raw.get("nome")
    key = raw.get("chave")
    valid = True
    if not isinstance(label, str) or not label.strip():
        result.add("MANIFEST_ITEMS_LABEL_REQUIRED", "itens.nome", "Informe o nome do item na tela (ex.: Empresa).")
        valid = False
    if not isinstance(key, str) or not ATTRIBUTE_PATTERN.fullmatch(key):
        result.add("MANIFEST_ITEMS_KEY_REQUIRED", "itens.chave", "Informe o atributo que identifica o item (ex.: codigo).")
        valid = False
    optional: dict[str, str | None] = {}
    for field_name in ("rotulo", "grupo"):
        value = raw.get(field_name)
        if value is not None and (not isinstance(value, str) or not ATTRIBUTE_PATTERN.fullmatch(value)):
            result.add("MANIFEST_ITEMS_ATTRIBUTE_INVALID", f"itens.{field_name}", f"itens.{field_name} deve ser um nome de atributo.")
            value = None
        optional[field_name] = value
    schema = raw.get("atributos")
    if schema is not None and (not isinstance(schema, dict) or schema.get("type", "object") != "object"):
        result.add("MANIFEST_ITEMS_SCHEMA_INVALID", "itens.atributos", "itens.atributos deve ser um JSON Schema de objeto.")
        schema = None
    work = raw.get("afetam_trabalho", [])
    if not isinstance(work, list) or not all(isinstance(w, str) and ATTRIBUTE_PATTERN.fullmatch(w) for w in work):
        result.add("MANIFEST_ITEMS_WORK_INVALID", "itens.afetam_trabalho", "afetam_trabalho deve ser uma lista de atributos.")
        work = []
    if schema is not None:
        declared = set(schema.get("properties", {}))
        for name in [*work, *(v for v in optional.values() if v)]:
            if name not in declared:
                result.add("MANIFEST_ITEMS_ATTRIBUTE_UNKNOWN", "itens", f"O atributo {name!r} não está em itens.atributos.")
    if not valid:
        return None
    return ItemSpec(
        label=label.strip(),
        key=key,
        label_attribute=optional["rotulo"],
        group_attribute=optional["grupo"],
        attributes_schema=schema,
        work_attributes=tuple(dict.fromkeys(work)),
    )


def _parse_steps(raw: Any, result: ValidationResult) -> tuple[StepSpec, ...]:
    """Lista ``etapas``, na ordem. Opcional."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        result.add("MANIFEST_STEPS_INVALID", "etapas", "etapas deve ser uma lista.")
        return ()
    steps: list[StepSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        path = f"etapas[{index}]"
        if not isinstance(entry, dict):
            result.add("MANIFEST_STEP_INVALID", path, "Cada etapa deve ser um mapeamento.")
            continue
        key = entry.get("chave")
        if not isinstance(key, str) or not STEP_KEY_PATTERN.fullmatch(key):
            result.add("MANIFEST_STEP_KEY_INVALID", f"{path}.chave", "Chave da etapa inválida (letras, números, _ . : -).")
            continue
        if key in seen:
            result.add("MANIFEST_STEP_DUPLICATED", f"{path}.chave", f"Etapa {key!r} repetida.")
            continue
        seen.add(key)
        raw_name = entry.get("nome")
        name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else key
        per_item = entry.get("por_item", True)
        per_task = entry.get("por_tarefa", False)
        if not isinstance(per_item, bool) or not isinstance(per_task, bool):
            result.add("MANIFEST_STEP_FLAG_INVALID", path, "por_item e por_tarefa devem ser true ou false.")
            continue
        steps.append(StepSpec(key=key, name=name, per_item=per_item, per_task=per_task))
    return tuple(steps)


def _parse_resources(raw_resources: Any, result: ValidationResult) -> ResourceRequirements:
    resources = raw_resources if isinstance(raw_resources, dict) else {}
    if raw_resources is not None and not isinstance(raw_resources, dict):
        result.add("MANIFEST_RESOURCES_INVALID", "resources", "resources must be a mapping.")
    cpu_units = resources.get("cpu_units", 1)
    memory_mb = resources.get("memory_mb", 512)
    disk_mb = resources.get("disk_mb", 100)
    for path, value in {
        "resources.cpu_units": cpu_units,
        "resources.memory_mb": memory_mb,
        "resources.disk_mb": disk_mb,
    }.items():
        if not isinstance(value, int) or value <= 0:
            result.add("MANIFEST_RESOURCE_INVALID", path, "Resource value must be a positive integer.")
    return ResourceRequirements(
        cpu_units=cpu_units if isinstance(cpu_units, int) and cpu_units > 0 else 1,
        memory_mb=memory_mb if isinstance(memory_mb, int) and memory_mb > 0 else 512,
        disk_mb=disk_mb if isinstance(disk_mb, int) and disk_mb > 0 else 100,
    )


def _parse_capability_requirements(raw_capabilities: Any, result: ValidationResult) -> list[CapabilityRequirement]:
    if raw_capabilities in (None, {}):
        return []
    if not isinstance(raw_capabilities, dict):
        result.add("MANIFEST_CAPABILITIES_INVALID", "capabilities", "capabilities must be a mapping.")
        return []
    raw_required = raw_capabilities.get("required", [])
    if not isinstance(raw_required, list):
        result.add("MANIFEST_CAPABILITIES_REQUIRED_INVALID", "capabilities.required", "capabilities.required must be a list.")
        return []
    requirements: list[CapabilityRequirement] = []
    for index, item in enumerate(raw_required):
        path = f"capabilities.required[{index}]"
        if isinstance(item, str):
            if not item.strip():
                result.add("MANIFEST_CAPABILITY_KEY_INVALID", path, "Capability key cannot be empty.")
                continue
            requirements.append(CapabilityRequirement(key=item.strip()))
            continue
        if isinstance(item, dict) and isinstance(item.get("key"), str) and item["key"].strip():
            requirements.append(
                CapabilityRequirement(
                    key=item["key"].strip(),
                    version=item.get("version") if isinstance(item.get("version"), str) else None,
                    attributes=item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
                )
            )
            continue
        result.add("MANIFEST_CAPABILITY_INVALID", path, "Capability items must be strings or objects with key.")
    return requirements


def _parse_string_list(raw_value: Any, path: str, result: ValidationResult) -> tuple[str, ...]:
    if raw_value in (None, []):
        return ()
    if not isinstance(raw_value, list) or not all(isinstance(item, str) and item.strip() for item in raw_value):
        result.add("MANIFEST_STRING_LIST_INVALID", path, "Expected a list of non-empty strings.")
        return ()
    return tuple(item.strip() for item in raw_value)


def _parse_schema_refs(raw_schemas: Any, result: ValidationResult) -> SchemaReferences:
    schemas = raw_schemas if isinstance(raw_schemas, dict) else {}
    if raw_schemas is not None and not isinstance(raw_schemas, dict):
        result.add("MANIFEST_SCHEMAS_INVALID", "schemas", "schemas must be a mapping.")
    input_schema = _optional_string(schemas, "input")
    output_schema = _optional_string(schemas, "output")
    for label, value in (("schemas.input", input_schema), ("schemas.output", output_schema)):
        if value and not _is_safe_relative_path(value):
            result.add("MANIFEST_SCHEMA_PATH_UNSAFE", label, "Schema path must be relative and inside the package.")
    return SchemaReferences(input=input_schema, output=output_schema)


def _is_safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    if path.is_absolute():
        return False
    if any(part in {"..", ""} for part in path.parts):
        return False
    return "\\" not in value and ":" not in value


def _is_path_ignored(relative_path: str, ignored_paths: list[str]) -> bool:
    return any(part in ignored_paths for part in PurePosixPath(relative_path).parts)


def _entrypoint_relative_path(entrypoint: dict[str, Any]) -> str | None:
    candidates = _entrypoint_relative_path_candidates(entrypoint)
    return candidates[0] if candidates else None


def _entrypoint_relative_path_candidates(entrypoint: dict[str, Any]) -> list[str]:
    # Regressao: isso so verificava um unico caminho fixo, com prefixo
    # "application/" hardcoded (application/<modulo>.py) - mas o Agent
    # (RuntimeLauncher.BuildPythonFunction / PythonFunctionLauncher.cs) faz
    # sys.path.insert(0, package_root) e importa o modulo diretamente, ou
    # seja, o layout real e correto e "<modulo>.py" na RAIZ do pacote (ex.:
    # "automation.main" -> "automation/main.py"), sem prefixo nenhum. Isso
    # fazia todo pacote python-function corretamente estruturado (mas sem um
    # "path" explicito no entrypoint) ser rejeitado com
    # MANIFEST_ENTRYPOINT_NOT_FOUND. Agora verifica a raiz primeiro (a
    # convencao que o Agent realmente usa), depois "src/" e "application/"
    # como convencoes alternativas ja aceitas em validate_entrypoint_on_disk.
    explicit_path = entrypoint.get("path")
    if isinstance(explicit_path, str):
        return [explicit_path]
    module = entrypoint.get("module")
    if isinstance(module, str):
        relative = PurePosixPath(*module.split(".")[:-1], f"{module.split('.')[-1]}.py")
        return [
            str(relative),
            str(PurePosixPath("src") / relative),
            str(PurePosixPath("application") / relative),
        ]
    return []


def _module_to_relative_path(module: str) -> Path:
    parts = module.split(".")
    return Path(*parts[:-1], f"{parts[-1]}.py") if len(parts) > 1 else Path(f"{parts[0]}.py")
