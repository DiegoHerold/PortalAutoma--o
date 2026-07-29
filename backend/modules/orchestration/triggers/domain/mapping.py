from __future__ import annotations

from typing import Any

_SOURCES = ("body", "headers", "query_params")


def apply_parameter_mapping(
    mapping: dict[str, str] | None,
    body: dict[str, Any],
    headers: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = headers or {}
    query_params = query_params or {}
    if not mapping:
        return {"webhook_data": body, "headers": headers, "query_params": query_params}

    sources = {"body": body, "headers": headers, "query_params": query_params}
    return {param_name: _resolve_path(dot_path, sources) for param_name, dot_path in mapping.items()}


def _resolve_path(dot_path: str, sources: dict[str, Any]) -> Any:
    parts = str(dot_path).split(".")
    if not parts:
        return None
    if parts[0] not in _SOURCES:
        parts = ["body", *parts]

    current: Any = sources.get(parts[0])
    for part in parts[1:]:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
            continue
        return None
    return current
