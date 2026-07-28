from __future__ import annotations

from copy import deepcopy
from typing import Any

from modules.telemetry.domain.errors import TelemetryValidationError
from modules.telemetry.domain.states import ExecutionEventType, ExecutionLogLevel, ExecutionMetricType


class DefaultEventPayloadValidator:
    def validate(self, event_type: str, payload: dict[str, Any], level: str | None = None) -> tuple[dict[str, Any], str | None, str | None]:
        try:
            event_type_enum = ExecutionEventType(event_type)
        except ValueError as exc:
            raise TelemetryValidationError(f"Unsupported event_type: {event_type}.") from exc
        if not isinstance(payload, dict):
            raise TelemetryValidationError("Event payload must be an object.")
        normalized = deepcopy(payload)
        normalized_level = _normalize_level(level or normalized.get("level"), event_type_enum)
        message = _message_from_payload(normalized, event_type_enum)

        if event_type_enum in {ExecutionEventType.LOG, ExecutionEventType.WARNING, ExecutionEventType.ERROR} and not message:
            raise TelemetryValidationError("Log, warning and error events require payload.message.")
        if event_type_enum == ExecutionEventType.TASK_PROGRESS:
            _validate_progress(normalized)
        if event_type_enum == ExecutionEventType.METRIC:
            _validate_metric(normalized)
        if event_type_enum in {ExecutionEventType.PROCESS_STARTED, ExecutionEventType.PROCESS_EXITED}:
            if not (normalized.get("process_id") or normalized.get("pid") or normalized.get("id")):
                raise TelemetryValidationError("Process events require process_id, id or pid.")
        return normalized, normalized_level, message


class RecursiveSecretMasker:
    SECRET_KEYS = {
        "authorization",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "client_secret",
        "password",
        "senha",
        "api_key",
        "apikey",
        "credential",
        "credentials",
    }

    def mask(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _mask_value(payload)


def _normalize_level(raw: Any, event_type: ExecutionEventType) -> str | None:
    if raw is None:
        if event_type == ExecutionEventType.ERROR:
            return ExecutionLogLevel.ERROR.value
        if event_type == ExecutionEventType.WARNING:
            return ExecutionLogLevel.WARNING.value
        if event_type == ExecutionEventType.LOG:
            return ExecutionLogLevel.INFO.value
        return None
    try:
        return ExecutionLogLevel(str(raw).upper()).value
    except ValueError as exc:
        raise TelemetryValidationError(f"Invalid log level: {raw}.") from exc


def _message_from_payload(payload: dict[str, Any], event_type: ExecutionEventType) -> str | None:
    for key in ("message", "error_message", "summary"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    if event_type == ExecutionEventType.ERROR and isinstance(payload.get("error"), dict):
        value = payload["error"].get("message")
        return str(value) if value is not None else None
    return None


def _validate_progress(payload: dict[str, Any]) -> None:
    percentage = payload.get("percentage") if "percentage" in payload else payload.get("progress")
    if percentage is not None:
        number = _as_number(percentage, "percentage")
        if number < 0 or number > 100:
            raise TelemetryValidationError("Progress percentage must be between 0 and 100.")
    current = payload.get("current")
    total = payload.get("total")
    if current is not None:
        current_number = _as_number(current, "current")
        if current_number < 0:
            raise TelemetryValidationError("Progress current must be positive.")
    if total is not None:
        total_number = _as_number(total, "total")
        if total_number < 0:
            raise TelemetryValidationError("Progress total must be positive.")


def _validate_metric(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get("metric_name"), str) or not payload.get("metric_name"):
        raise TelemetryValidationError("Metric events require metric_name.")
    _as_number(payload.get("value"), "value")
    metric_type = payload.get("metric_type") or ExecutionMetricType.GAUGE.value
    try:
        ExecutionMetricType(str(metric_type))
    except ValueError as exc:
        raise TelemetryValidationError(f"Invalid metric_type: {metric_type}.") from exc


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise TelemetryValidationError(f"{field} must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TelemetryValidationError(f"{field} must be numeric.") from exc


def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in RecursiveSecretMasker.SECRET_KEYS:
                masked[key] = "***"
            else:
                masked[key] = _mask_value(item)
        return masked
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    return value
