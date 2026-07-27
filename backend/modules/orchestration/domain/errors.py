from __future__ import annotations


class OrchestrationError(Exception):
    """Base error for execution orchestration rules."""


class InvalidExecutionTransition(OrchestrationError):
    """Raised when an execution state transition is not allowed."""


class AutomationVersionNotExecutable(OrchestrationError):
    """Raised when an AutomationVersion cannot be executed."""


class ExecutionNotFound(OrchestrationError):
    """Raised when an execution entity cannot be found."""


class ExecutionSecurityError(OrchestrationError):
    """Raised when an agent message does not match the committed execution."""


class IdempotencyConflict(OrchestrationError):
    """Raised when an Idempotency-Key is reused with a different payload."""
