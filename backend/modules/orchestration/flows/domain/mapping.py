from __future__ import annotations

from typing import Any


class MappingError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def resolve_mapping(mapping: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    if not mapping:
        return dict(context.get("flow", {}).get("input") or {})
    resolved: dict[str, Any] = {}
    for key, spec in mapping.items():
        resolved[key] = resolve_value(spec, context)
    return resolved


def resolve_value(spec: Any, context: dict[str, Any]) -> Any:
    if not isinstance(spec, dict):
        return spec
    if "value" in spec:
        return spec["value"]
    source = str(spec.get("source") or "")
    path = str(spec.get("path") or "$")
    source_value = _source_value(source, context)
    return _path(source_value, path)


def evaluate_condition(condition: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    if not condition:
        return {"matched": True, "reason": "no_condition"}
    matched = bool(_eval(condition, context, depth=0))
    return {"matched": matched, "condition": condition}


def _eval(condition: dict[str, Any], context: dict[str, Any], depth: int) -> bool:
    if depth > 8:
        raise MappingError("CONDITION_TOO_DEEP", "Condicao excede a profundidade maxima.")
    operator = condition.get("operator")
    if operator == "and":
        return all(_eval(item, context, depth + 1) for item in condition.get("conditions") or [])
    if operator == "or":
        return any(_eval(item, context, depth + 1) for item in condition.get("conditions") or [])
    if operator == "not":
        return not _eval(condition.get("condition") or {}, context, depth + 1)
    left = resolve_value(condition.get("left"), context)
    right = resolve_value(condition.get("right"), context) if isinstance(condition.get("right"), dict) else condition.get("right")
    if operator == "equals":
        return left == right
    if operator == "not_equals":
        return left != right
    if operator == "exists":
        return left is not None
    if operator == "greater_than":
        return float(left) > float(right)
    if operator == "less_than":
        return float(left) < float(right)
    raise MappingError("CONDITION_OPERATOR_INVALID", "Operador de condicao invalido.", {"operator": operator})


def _source_value(source: str, context: dict[str, Any]) -> Any:
    if source == "flow.input":
        return context.get("flow", {}).get("input")
    if source == "flow.metadata":
        return context.get("flow", {}).get("metadata")
    if source.startswith("node.") and source.endswith(".output"):
        key = source.removeprefix("node.").removesuffix(".output")
        return (context.get("nodes") or {}).get(key, {}).get("output")
    if source.startswith("node.") and source.endswith(".status"):
        key = source.removeprefix("node.").removesuffix(".status")
        return (context.get("nodes") or {}).get(key, {}).get("status")
    raise MappingError("MAPPING_SOURCE_INVALID", "Fonte de mapping invalida.", {"source": source})


def _path(value: Any, path: str) -> Any:
    if path in {"", "$"}:
        return value
    if not path.startswith("$."):
        raise MappingError("MAPPING_PATH_INVALID", "Path deve usar sintaxe $.campo.subcampo.", {"path": path})
    current = value
    for part in path[2:].split("."):
        if not part or part.startswith("_"):
            raise MappingError("MAPPING_PATH_INVALID", "Path contem segmento invalido.", {"path": path})
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
