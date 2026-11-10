from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ActorDTO:
    actor_type: str
    actor_id: str | None = None
    actor_email: str | None = None
    ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class AutomationVersionSnapshotDTO:
    automation_id: int
    automation_key: str | None
    automation_name: str
    automation_version_id: int
    version: str
    status: str
    runtime_id: str
    runtime_version: str | None
    runtime_version_id: str | None
    package_id: str
    package_sha256: str
    package_size_bytes: int
    package_download_url: str | None
    manifest: dict[str, Any]
    execution_mode: str
    timeout_seconds: int
    resources: dict[str, int]
    required_capabilities: list[dict[str, Any]]
    required_pools: list[str]
    exclusive_resources: list[str]
    retry_policy: dict[str, Any] = field(default_factory=dict)
    timeout_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionDTO:
    id: str
    type: str
    origin: str
    status: str
    requested_by: str | None
    organization_id: str | None
    input: dict[str, Any]
    result: dict[str, Any] | None
    correlation_id: str | None
    idempotency_key: str | None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_summary: str | None = None
    legacy_job_id: int | None = None


@dataclass(frozen=True)
class TaskExecutionDTO:
    id: str
    execution_id: str
    automation_version_id: int
    status: str
    priority: int
    parameters: dict[str, Any]
    input: dict[str, Any]
    result: dict[str, Any] | None
    retry_policy: dict[str, Any]
    timeout_policy: dict[str, Any]
    created_at: datetime
    ready_at: datetime | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_attempt_number: int = 0
    failure_summary: str | None = None
    requirements_snapshot: dict[str, Any] = field(default_factory=dict)
    available_at: datetime | None = None
    scheduling_attempts: int = 0
    last_scheduling_attempt_at: datetime | None = None
    next_scheduling_attempt_at: datetime | None = None
    last_scheduling_failure: dict[str, Any] | None = None
    group_key: str | None = None
    dedup_key: str | None = None
    manual_position: int | None = None
    enqueue_batch_id: str | None = None
    enqueued_at: datetime | None = None
    pool: str | None = None
    required_machine_id: str | None = None
    lost_at: datetime | None = None


@dataclass(frozen=True)
class ExecutionAttemptDTO:
    id: str
    task_execution_id: str
    attempt_number: int
    agent_id: str | None
    agent_instance_id: str | None
    status: str
    runtime_version_id: str | None
    package_id: str | None
    offer_id: str | None
    created_at: datetime
    offered_at: datetime | None = None
    accepted_at: datetime | None = None
    committed_at: datetime | None = None
    preparing_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    exit_code: int | None = None
    output: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    resource_usage: dict[str, Any] | None = None
    executor_type: str = "agent"
    executor_id: str | None = None
    machine_id: str | None = None


@dataclass(frozen=True)
class ExecutionOfferDTO:
    id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    status: str
    requirements_snapshot: dict[str, Any]
    offered_at: datetime
    expires_at: datetime
    responded_at: datetime | None = None
    accepted_at: datetime | None = None
    committed_at: datetime | None = None
    rejection_code: str | None = None
    rejection_details: dict[str, Any] | None = None
    correlation_id: str | None = None
    commit_token_expires_at: datetime | None = None


@dataclass(frozen=True)
class ResourceReservationDTO:
    id: str
    execution_offer_id: str | None
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    pool_type: str
    quantity: int
    status: str
    expires_at: datetime
    created_at: datetime
    released_at: datetime | None = None
    converted_at: datetime | None = None
    task_execution_id: str | None = None
    units: int | None = None
    reserved_at: datetime | None = None
    activated_at: datetime | None = None
    release_reason: str | None = None


@dataclass(frozen=True)
class AgentSelectionRequestDTO:
    automation_version: AutomationVersionSnapshotDTO
    preferred_agent_id: str | None
    execution_mode: str
    required_capabilities: list[dict[str, Any]]
    required_pools: list[str]


@dataclass(frozen=True)
class AgentSelectionDTO:
    agent_id: str
    agent_instance_id: str
    worker_id: int | None
    reason: str
    pools: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateAutomationExecutionCommand:
    automation_version_id: int
    actor: ActorDTO
    parameters: dict[str, Any]
    priority: int = 0
    agent_id: str | None = None
    origin: str = "manual"
    correlation_id: str | None = None
    idempotency_key: str | None = None
    request_hash: str | None = None
    organization_id: str | None = None


@dataclass(frozen=True)
class ExecutionSummaryDTO:
    """Enriched read model for list views (replaces the legacy Job mirror).

    to_payload() flattens `execution`'s fields to the top level and adds the
    enrichment fields as siblings, so the wire format stays a strict
    superset of ExecutionDTO/ExecutionResponse — existing consumers of
    GET /executions that only read the base fields (id, status, started_at,
    completed_at, failure_summary, legacy_job_id...) keep working unchanged.
    """

    execution: ExecutionDTO
    automation_id: int | None
    automation_name: str | None
    priority: int | None
    agent_id: str | None
    agent_name: str | None
    worker_id: int | None

    def to_payload(self) -> dict[str, Any]:
        payload = _json(asdict(self.execution))
        payload.update(
            {
                "automation_id": self.automation_id,
                "automation_name": self.automation_name,
                "priority": self.priority,
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "worker_id": self.worker_id,
            }
        )
        return payload


@dataclass(frozen=True)
class ExecutionDetailsDTO:
    execution: ExecutionDTO
    tasks: list[TaskExecutionDTO]
    attempts: list[ExecutionAttemptDTO]
    current_attempt: ExecutionAttemptDTO | None
    current_offer: ExecutionOfferDTO | None
    agent: dict[str, Any] | None
    automation_version: AutomationVersionSnapshotDTO | None

    def to_payload(self) -> dict[str, Any]:
        return _json(asdict(self))


def _json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return value
