"""
Pure logic for turning an incoming webhook payload into the parameters an
automation actually receives, based on the Trigger's parameter_mapping_json.

No DB dependency (mirrors the style of app/domain/recurrence.py).

Mapping notation: `{"parameter_name": "dot.path.into.source"}`. The first
segment of the dot-path selects the source -- "body", "headers", or
"query_params" -- and the remaining segments walk into that source's
dict/list structure. A path with no recognized source prefix is treated as
relative to "body" (so "cnpj" and "body.cnpj" are equivalent). Missing
paths resolve to None rather than raising, so a slightly-off mapping does
not break the whole dispatch -- the automation receives None for that
parameter and can decide how to handle it.

If no mapping is configured, the original raw webhook shape is preserved
(`{"webhook_data": body, "headers": ..., "query_params": ...}`) so triggers
created before parameter mapping existed keep working unchanged.
"""

from typing import Any

_SOURCES = ("body", "headers", "query_params")


def _resolve_path(dot_path: str, sources: dict[str, Any]) -> Any:
    parts = dot_path.split(".")
    if parts[0] not in _SOURCES:
        parts = ["body", *parts]

    current: Any = sources.get(parts[0])
    for part in parts[1:]:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def apply_parameter_mapping(
    mapping: dict[str, str] | None,
    body: dict,
    headers: dict | None = None,
    query_params: dict | None = None,
) -> dict:
    headers = headers or {}
    query_params = query_params or {}

    if not mapping:
        return {"webhook_data": body, "headers": headers, "query_params": query_params}

    sources = {"body": body, "headers": headers, "query_params": query_params}
    return {param_name: _resolve_path(dot_path, sources) for param_name, dot_path in mapping.items()}
