from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DispatchCandidateDTO:
    agent_id: str
    agent_instance_id: str | None
    eligible: bool
    rejection_reasons: list[dict[str, Any]]
    score: float
    score_components: dict[str, float]
    evaluated_at: datetime
    snapshot_revision: int | None = None
    worker_id: int | None = None


@dataclass(frozen=True)
class DispatchDecisionDTO:
    id: str
    scheduler_run_id: str
    task_execution_id: str
    status: str
    candidates: list[dict[str, Any]]
    weights: dict[str, float]
    created_at: datetime
    execution_attempt_id: str | None = None
    execution_offer_id: str | None = None
    selected_agent_id: str | None = None
    selected_agent_instance_id: str | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceReservationDTO:
    id: str
    task_execution_id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    pool_type: str
    units: int
    status: str
    reserved_at: datetime
    expires_at: datetime
    execution_offer_id: str | None = None
    activated_at: datetime | None = None
    released_at: datetime | None = None
    release_reason: str | None = None


@dataclass(frozen=True)
class ResourceLockDTO:
    id: str
    resource_key: str
    normalized_key: str
    scope: str
    agent_id: str
    execution_attempt_id: str
    status: str
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None
    release_reason: str | None = None


@dataclass(frozen=True)
class ExecutionLeaseDTO:
    id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    status: str
    issued_at: datetime
    expires_at: datetime
    last_renewed_at: datetime | None
    renewal_sequence: int
    grace_until: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None


@dataclass(frozen=True)
class RetryScheduleDTO:
    id: str
    task_execution_id: str
    source_attempt_id: str
    attempt_number: int
    retry_number: int
    reason: str
    status: str
    available_at: datetime
    created_at: datetime
    error_code: str | None = None
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class CancellationRequestDTO:
    id: str
    execution_id: str
    task_execution_id: str | None
    execution_attempt_id: str | None
    status: str
    requested_by: str | None
    reason: str | None
    requested_at: datetime
    graceful_until: datetime | None = None
    force_after: datetime | None = None
    command_id: str | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class ReconciliationRecordDTO:
    id: str
    kind: str
    status: str
    decision: str
    details: dict[str, Any]
    created_at: datetime
    agent_id: str | None = None
    agent_instance_id: str | None = None
    execution_attempt_id: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class AgentSyncExecutionDTO:
    execution_id: str | None
    execution_attempt_id: str | None
    state: str | None
    reservation_id: str | None = None
    workspace_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentSyncStateCommand:
    agent_id: str
    agent_instance_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AgentSyncStateResultDTO:
    agent_id: str
    agent_instance_id: str
    reason: str | None
    summary: dict[str, int]
    decisions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    reservations: dict[str, Any]
    leases: dict[str, Any]
    artifacts: dict[str, Any]
    recorded_at: datetime


@dataclass(frozen=True)
class AgentDispatchSnapshotDTO:
    agent_id: str
    agent_instance_id: str | None
    worker_id: int | None
    enabled: bool
    connectivity_status: str
    administrative_status: str
    health_status: str
    occupancy_status: str
    protocol_version: str | None
    agent_version: str | None
    last_seen_at: datetime | None
    snapshot_observed_at: datetime | None
    snapshot_expires_at: datetime | None
    snapshot_revision: int | None
    cpu_usage_percentage: float | None
    memory_available_mb: int | None
    disk_free_mb: int | None
    machine_profile: dict[str, Any] | None
    capabilities: list[dict[str, Any]]
    pools: dict[str, dict[str, Any]]
    interactive_session: dict[str, Any] | None
    active_attempts: int = 0


@dataclass(frozen=True)
class ScheduleTaskResultDTO:
    task_execution_id: str
    scheduled: bool
    decision_id: str
    execution_attempt_id: str | None = None
    execution_offer_id: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None
    command_id: str | None = None
    next_scheduling_attempt_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ScheduleReadyTasksResultDTO:
    scheduler_run_id: str
    scanned: int
    scheduled: int
    skipped: int
    results: list[ScheduleTaskResultDTO]


@dataclass(frozen=True)
class LeaseRenewalCommand:
    execution_attempt_id: str
    lease_id: str
    renewal_sequence: int
    running: bool
    observed_at: datetime | None
    agent_id: str
    agent_instance_id: str


def to_payload(value: Any) -> Any:
    if is_dataclass(value):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
