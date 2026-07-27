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
    manifest: dict[str, Any]
    execution_mode: str
    timeout_seconds: int
    resources: dict[str, int]
    required_capabilities: list[dict[str, Any]]
    required_pools: list[str]
    exclusive_resources: list[str]


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


@dataclass(frozen=True)
class ExecutionAttemptDTO:
    id: str
    task_execution_id: str
    attempt_number: int
    agent_id: str
    agent_instance_id: str
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
    execution_offer_id: str
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
