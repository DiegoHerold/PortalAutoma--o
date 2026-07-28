from __future__ import annotations


class TelemetryError(ValueError):
    """Base error for telemetry validation and routing failures."""


class TelemetryValidationError(TelemetryError):
    """Raised when a batch is structurally invalid and must be rejected atomically."""


class ExecutionAttemptTelemetryError(TelemetryError):
    """Raised when an event is reported for the wrong Agent, instance, or attempt."""


class TelemetryNotFound(TelemetryError):
    """Raised when telemetry is requested for an unknown execution resource."""
