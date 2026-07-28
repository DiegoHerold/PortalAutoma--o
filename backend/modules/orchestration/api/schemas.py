from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionCreateRequest(BaseModel):
    automation_version_id: int | str
    agent_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class ExecutionResponse(BaseModel):
    id: str
    type: str
    origin: str
    status: str
    requested_by: str | None = None
    organization_id: str | None = None
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_summary: str | None = None
    legacy_job_id: int | None = None


class TaskExecutionResponse(BaseModel):
    id: str
    execution_id: str
    automation_version_id: int
    status: str
    priority: int
    parameters: dict[str, Any]
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    requirements_snapshot: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any]
    timeout_policy: dict[str, Any]
    created_at: datetime
    ready_at: datetime | None = None
    queued_at: datetime | None = None
    available_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_attempt_number: int
    scheduling_attempts: int = 0
    last_scheduling_attempt_at: datetime | None = None
    next_scheduling_attempt_at: datetime | None = None
    last_scheduling_failure: dict[str, Any] | None = None
    failure_summary: str | None = None


class ExecutionAttemptResponse(BaseModel):
    id: str
    task_execution_id: str
    attempt_number: int
    agent_id: str
    agent_instance_id: str
    status: str
    runtime_version_id: str | None = None
    package_id: str | None = None
    offer_id: str | None = None
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


class ExecutionOfferResponse(BaseModel):
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


class ExecutionDetailsResponse(BaseModel):
    execution: ExecutionResponse
    tasks: list[TaskExecutionResponse]
    attempts: list[ExecutionAttemptResponse]
    current_attempt: ExecutionAttemptResponse | None = None
    current_offer: ExecutionOfferResponse | None = None
    agent: dict[str, Any] | None = None
    automation_version: dict[str, Any] | None = None
    telemetry: dict[str, Any] | None = None
