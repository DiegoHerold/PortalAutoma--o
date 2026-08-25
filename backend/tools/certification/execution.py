"""Create and observe certification executions through the real Portal API.

Per docs/certification-harness.md item 43-46: executions are created with
`POST /executions` (never inserted into the database directly), and
observation polls `GET /executions/{id}` (+ /tasks, /attempts,
/artifacts) — the same endpoints the frontend uses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from tools.certification.api_client import PortalApiClient

# Real terminal execution states, per docs/execution-lifecycle.md /
# domain state machine. TIMED_OUT and CANCELLED are terminal alongside
# SUCCEEDED and FAILED.
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timed_out"}


class ExecutionTimeoutError(RuntimeError):
    """The harness's own poll budget was exceeded — NOT the same thing as
    the execution itself reaching a TIMED_OUT terminal state. Section 51 of
    docs/certification-harness.md is explicit that a harness poll timeout
    must never be reported as PASS."""


@dataclass
class ObservedExecution:
    execution_id: str
    status: str
    task_status: str | None
    attempt_status: str | None
    result: dict[str, Any] | None
    error_output: str | None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def create_certification_execution(
    client: PortalApiClient,
    automation_version_id: int,
    *,
    agent_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    idempotency_key = f"certification-{run_id or 'run'}-{uuid4().hex}"
    return client.create_execution(
        automation_version_id,
        agent_id=agent_id,
        parameters=parameters,
        idempotency_key=idempotency_key,
    )


def observe_execution(client: PortalApiClient, execution_id: str) -> ObservedExecution:
    details = client.get_execution(execution_id)
    execution = details.get("execution", {})
    tasks = details.get("tasks") or [{}]
    attempt = details.get("current_attempt") or {}

    try:
        artifacts = client.get_execution_artifacts(execution_id)
    except Exception:
        # Artifact listing is best-effort for observation; a failure here
        # must not hide the execution's actual terminal status.
        artifacts = []

    return ObservedExecution(
        execution_id=execution_id,
        status=execution.get("status", "unknown"),
        task_status=tasks[0].get("status") if tasks else None,
        attempt_status=attempt.get("status"),
        result=execution.get("result") or attempt.get("result"),
        error_output=_extract_error_output(execution, attempt),
        artifacts=artifacts,
        raw=details,
    )


def wait_until_terminal(
    client: PortalApiClient,
    execution_id: str,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 1.0,
) -> ObservedExecution:
    """Poll GET /executions/{id} until the Portal-side status is terminal or
    the harness's own timeout_seconds budget runs out.

    Raises ExecutionTimeoutError on budget exhaustion instead of returning a
    fabricated terminal state — the caller decides how to report that
    (BLOCKED, not PASS)."""

    deadline = time.monotonic() + timeout_seconds
    last: ObservedExecution | None = None
    while time.monotonic() < deadline:
        last = observe_execution(client, execution_id)
        if last.status in TERMINAL_STATUSES:
            return last
        time.sleep(poll_interval_seconds)

    raise ExecutionTimeoutError(
        f"execution {execution_id} did not reach a terminal status within {timeout_seconds}s "
        f"(last observed status: {last.status if last else 'unknown'})"
    )


def wait_until_status(
    client: PortalApiClient,
    execution_id: str,
    *,
    statuses: set[str],
    timeout_seconds: float,
    poll_interval_seconds: float = 1.0,
) -> ObservedExecution:
    deadline = time.monotonic() + timeout_seconds
    last: ObservedExecution | None = None
    while time.monotonic() < deadline:
        last = observe_execution(client, execution_id)
        observed_statuses = {
            item
            for item in (last.status, last.task_status, last.attempt_status)
            if item is not None
        }
        if observed_statuses & statuses:
            return last
        if last.status in TERMINAL_STATUSES:
            return last
        time.sleep(poll_interval_seconds)

    raise ExecutionTimeoutError(
        f"execution {execution_id} did not reach one of {sorted(statuses)} within {timeout_seconds}s "
        f"(last observed status: {last.status if last else 'unknown'})"
    )


def _extract_error_output(execution: dict[str, Any], attempt: dict[str, Any]) -> str | None:
    candidates: list[Any] = [
        attempt.get("error_output"),
        attempt.get("error_message"),
        execution.get("error_output"),
        execution.get("failure_summary"),
        _nested(attempt.get("result"), "error", "message"),
        _nested(execution.get("result"), "error", "message"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def _nested(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
