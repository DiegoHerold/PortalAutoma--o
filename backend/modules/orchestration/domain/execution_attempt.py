from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from modules.orchestration.domain.errors import InvalidExecutionTransition
from modules.orchestration.domain.states import EXECUTION_ATTEMPT_TRANSITIONS, ExecutionAttemptStatus


@dataclass(frozen=True)
class ExecutionAttempt:
    id: str
    task_execution_id: str
    attempt_number: int
    agent_id: str
    agent_instance_id: str
    status: ExecutionAttemptStatus
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

    @classmethod
    def create(
        cls,
        *,
        id: str,
        task_execution_id: str,
        attempt_number: int,
        agent_id: str,
        agent_instance_id: str,
        runtime_version_id: str | None,
        package_id: str | None,
        now: datetime,
    ) -> "ExecutionAttempt":
        if attempt_number <= 0:
            raise ValueError("ExecutionAttempt attempt_number must be positive.")
        if not agent_id or not agent_instance_id:
            raise ValueError("ExecutionAttempt requires an Agent and AgentInstance.")
        return cls(
            id=id,
            task_execution_id=task_execution_id,
            attempt_number=attempt_number,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            status=ExecutionAttemptStatus.CREATED,
            runtime_version_id=runtime_version_id,
            package_id=package_id,
            offer_id=None,
            created_at=now,
        )

    def mark_offered(self, offer_id: str, now: datetime) -> "ExecutionAttempt":
        return self._transition(ExecutionAttemptStatus.OFFERED, offer_id=offer_id, offered_at=now)

    def mark_accepted(self, now: datetime) -> "ExecutionAttempt":
        if self.status == ExecutionAttemptStatus.ACCEPTED:
            return self
        return self._transition(ExecutionAttemptStatus.ACCEPTED, accepted_at=self.accepted_at or now)

    def mark_rejected(self, code: str, message: str | None, now: datetime) -> "ExecutionAttempt":
        return self._transition(ExecutionAttemptStatus.REJECTED, error_code=code, error_message=message)

    def mark_expired(self, now: datetime) -> "ExecutionAttempt":
        return self._transition(ExecutionAttemptStatus.EXPIRED, error_code="OFFER_EXPIRED")

    def mark_committed(self, now: datetime) -> "ExecutionAttempt":
        if self.status == ExecutionAttemptStatus.COMMITTED:
            return self
        return self._transition(ExecutionAttemptStatus.COMMITTED, committed_at=self.committed_at or now)

    def mark_preparing(self, now: datetime) -> "ExecutionAttempt":
        if self.status == ExecutionAttemptStatus.PREPARING:
            return self
        return self._transition(ExecutionAttemptStatus.PREPARING, preparing_at=self.preparing_at or now)

    def mark_running(self, now: datetime) -> "ExecutionAttempt":
        if self.status == ExecutionAttemptStatus.RUNNING:
            return self
        if self.status == ExecutionAttemptStatus.COMMITTED:
            return replace(
                self,
                status=ExecutionAttemptStatus.RUNNING,
                preparing_at=self.preparing_at or now,
                started_at=self.started_at or now,
            )
        return self._transition(ExecutionAttemptStatus.RUNNING, started_at=self.started_at or now)

    def _transition(self, status: ExecutionAttemptStatus, **changes: Any) -> "ExecutionAttempt":
        if status not in EXECUTION_ATTEMPT_TRANSITIONS.get(self.status, set()):
            raise InvalidExecutionTransition(f"ExecutionAttempt cannot transition from {self.status} to {status}.")
        return replace(self, status=status, **changes)
