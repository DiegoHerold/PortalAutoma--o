from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from modules.dispatch.application.dto import CancellationRequestDTO, RetryScheduleDTO
from modules.dispatch.application.ports import (
    AgentCommandPort,
    CancellationRequestRepository,
    ExecutionLeaseRepository,
    OfferReservationPort,
    OutboxPort,
    ResourceLockRepository,
    RetryScheduleRepository,
    TransactionManager,
)
from modules.orchestration.application.dto import ActorDTO, ExecutionAttemptDTO, ExecutionDTO, TaskExecutionDTO
from modules.orchestration.application.ports import ExecutionAttemptRepository, ExecutionRepository, TaskExecutionRepository


TERMINAL_EXECUTION_STATUSES = {"succeeded", "failed", "cancelled", "timed_out"}
TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled", "timed_out", "skipped"}
ACTIVE_ATTEMPT_STATUSES = {"offered", "accepted", "committed", "preparing", "running", "cancel_requested"}


class EvaluateRetryPolicy:
    def execute(self, task: TaskExecutionDTO, attempt: ExecutionAttemptDTO, *, reason: str, error_code: str | None = None) -> dict[str, Any]:
        policy = task.retry_policy or {}
        max_attempts = _positive_int(policy.get("max_attempts"), _positive_int(policy.get("max_retries"), 0) + 1)
        if attempt.attempt_number >= max_attempts:
            return {"retry": False, "reason": "max_attempts_reached", "max_attempts": max_attempts}
        non_retryable = set(policy.get("non_retryable_error_codes") or [])
        if error_code and error_code in non_retryable:
            return {"retry": False, "reason": "non_retryable_error_code", "error_code": error_code}
        if reason == "lost" and not bool(policy.get("retry_on_lost", True)):
            return {"retry": False, "reason": "retry_on_lost_disabled"}
        if reason == "timeout" and not bool(policy.get("retry_on_timeout", False)):
            return {"retry": False, "reason": "retry_on_timeout_disabled"}
        retryable = set(policy.get("retryable_error_codes") or [])
        if retryable and error_code and error_code not in retryable and reason not in {"lost", "timeout"}:
            return {"retry": False, "reason": "error_code_not_retryable", "error_code": error_code}
        initial = _positive_int(policy.get("initial_delay_seconds"), 5)
        max_delay = _positive_int(policy.get("max_delay_seconds"), 300)
        multiplier = policy.get("backoff_multiplier") if isinstance(policy.get("backoff_multiplier"), (int, float)) else 2
        delay = min(max_delay, int(initial * (float(multiplier) ** max(attempt.attempt_number - 1, 0))))
        return {"retry": True, "delay_seconds": delay, "next_attempt_number": attempt.attempt_number + 1, "max_attempts": max_attempts}


class ScheduleTaskRetry:
    def __init__(self, tasks: TaskExecutionRepository, attempts: ExecutionAttemptRepository, retry_schedules: RetryScheduleRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.tasks = tasks
        self.attempts = attempts
        self.retry_schedules = retry_schedules
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, task_execution_id: str, source_attempt_id: str, reason: str, error_code: str | None = None) -> dict[str, Any]:
        task = _require_task(self.tasks, task_execution_id)
        attempt = _require_attempt(self.attempts, source_attempt_id)
        decision = EvaluateRetryPolicy().execute(task, attempt, reason=reason, error_code=error_code)
        if not decision.get("retry"):
            return decision
        now = utcnow()
        available_at = now + timedelta(seconds=int(decision["delay_seconds"]))
        saved_task = self.tasks.save(
            replace(
                task,
                status="ready",
                ready_at=now,
                available_at=available_at,
                next_scheduling_attempt_at=available_at,
                last_scheduling_failure={"code": "RETRY_SCHEDULED", "reason": reason, "source_attempt_id": source_attempt_id},
            )
        )
        schedule = self.retry_schedules.add(
            RetryScheduleDTO(
                id=new_id("retry"),
                task_execution_id=task.id,
                source_attempt_id=attempt.id,
                attempt_number=attempt.attempt_number + 1,
                retry_number=attempt.attempt_number,
                reason=reason,
                error_code=error_code,
                status="scheduled",
                available_at=available_at,
                created_at=now,
            )
        )
        self.outbox.append_event("execution.retry_scheduled", "task_execution", task.id, {"task_execution_id": task.id, "retry_schedule_id": schedule.id, "available_at": available_at.isoformat()})
        self.transaction.commit()
        return {"retry": True, "retry_schedule_id": schedule.id, "available_at": available_at, "task_execution_id": saved_task.id}


class RequestExecutionCancellation:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        cancellation_requests: CancellationRequestRepository,
        commands: AgentCommandPort,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        leases: ExecutionLeaseRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.cancellation_requests = cancellation_requests
        self.commands = commands
        self.reservations = reservations
        self.locks = locks
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, execution_id: str, *, actor: ActorDTO, reason: str | None = None) -> dict[str, Any]:
        execution = _require_execution(self.executions, execution_id)
        if execution.status in TERMINAL_EXECUTION_STATUSES:
            self.transaction.commit()
            return {"execution_id": execution.id, "status": execution.status, "idempotent": True}
        current = self.cancellation_requests.current_for_execution(execution_id)
        if current is not None:
            self.transaction.commit()
            return {"execution_id": execution.id, "cancellation_request_id": current.id, "status": current.status, "idempotent": True}
        now = utcnow()
        tasks = self.tasks.list_for_execution(execution_id)
        attempts = self.attempts.list_for_execution(execution_id)
        active_attempt = _current_active_attempt(attempts)
        task = next((item for item in reversed(tasks) if item.status not in TERMINAL_TASK_STATUSES), tasks[-1] if tasks else None)
        if task is None or active_attempt is None or active_attempt.status in {"created", "offered", "accepted"}:
            for item in tasks:
                if item.status not in TERMINAL_TASK_STATUSES:
                    self.tasks.save(replace(item, status="cancelled", completed_at=now, failure_summary=reason or "Execution cancelled before dispatch."))
            self.executions.save(replace(execution, status="cancelled", completed_at=now, failure_summary=reason or "Execution cancelled before dispatch."))
            if active_attempt is not None:
                self.attempts.save(replace(active_attempt, status="cancelled", completed_at=now, error_code="EXECUTION_CANCELLED", error_message=reason))
                self.reservations.release_for_attempt(active_attempt.id, now, "cancelled_before_start")
                self.locks.release_for_attempt(active_attempt.id, now, "cancelled_before_start")
            request = self.cancellation_requests.add(
                CancellationRequestDTO(
                    id=new_id("can"),
                    execution_id=execution.id,
                    task_execution_id=task.id if task else None,
                    execution_attempt_id=active_attempt.id if active_attempt else None,
                    status="confirmed",
                    requested_by=actor.actor_id,
                    reason=reason,
                    requested_at=now,
                    completed_at=now,
                )
            )
            self.outbox.append_event("execution.cancelled", "execution", execution.id, {"execution_id": execution.id, "cancellation_request_id": request.id})
            self.transaction.commit()
            return {"execution_id": execution.id, "status": "cancelled", "cancellation_request_id": request.id}

        policy = task.timeout_policy or {}
        graceful = _positive_int(policy.get("graceful_cancel_seconds"), 30)
        force = _positive_int(policy.get("force_cancel_seconds"), 120)
        graceful_until = now + timedelta(seconds=graceful)
        force_after = now + timedelta(seconds=force)
        command = self.commands.create(
            active_attempt.agent_id,
            "execution.cancel",
            {
                "execution_id": execution.id,
                "task_execution_id": active_attempt.task_execution_id,
                "execution_attempt_id": active_attempt.id,
                "reason": reason or "cancel_requested",
                "graceful_until": graceful_until.isoformat(),
                "force_after": force_after.isoformat(),
            },
            expires_at=force_after,
        )
        self.executions.save(replace(execution, status="cancelling", started_at=execution.started_at or now))
        self.tasks.save(replace(task, status="cancelling", started_at=task.started_at or now))
        self.attempts.save(replace(active_attempt, status="cancel_requested", error_code="CANCEL_REQUESTED", error_message=reason))
        request = self.cancellation_requests.add(
            CancellationRequestDTO(
                id=new_id("can"),
                execution_id=execution.id,
                task_execution_id=task.id,
                execution_attempt_id=active_attempt.id,
                status="command_sent",
                requested_by=actor.actor_id,
                reason=reason,
                requested_at=now,
                graceful_until=graceful_until,
                force_after=force_after,
                command_id=command.id,
            )
        )
        self.outbox.append_event("execution.cancel_requested", "execution", execution.id, {"execution_id": execution.id, "execution_attempt_id": active_attempt.id, "command_id": command.id})
        self.transaction.commit()
        return {"execution_id": execution.id, "status": "cancelling", "cancellation_request_id": request.id, "command_id": command.id}


class ForceCancelExecutionAttempt:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        cancellation_requests: CancellationRequestRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        leases: ExecutionLeaseRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.cancellation_requests = cancellation_requests
        self.reservations = reservations
        self.locks = locks
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute_due(self, *, limit: int = 100) -> dict[str, int]:
        now = utcnow()
        count = 0
        for request in self.cancellation_requests.due_for_force(now, limit=limit):
            if request.execution_attempt_id:
                attempt = self.attempts.get(request.execution_attempt_id)
                if attempt is not None and attempt.status in ACTIVE_ATTEMPT_STATUSES:
                    self.attempts.save(replace(attempt, status="lost", completed_at=now, error_code="FORCED_CANCELLATION", error_message="Cancellation was forced after grace period. Agent process may still be running locally."))
                    self.reservations.release_for_attempt(attempt.id, now, "forced_cancellation")
                    self.locks.release_for_attempt(attempt.id, now, "forced_cancellation")
                    lease = self.leases.active_for_attempt(attempt.id)
                    if lease is not None:
                        self.leases.save(replace(lease, status="revoked", revoked_at=now, revocation_reason="forced_cancellation"))
            execution = self.executions.get(request.execution_id)
            if execution is not None and execution.status not in TERMINAL_EXECUTION_STATUSES:
                self.executions.save(replace(execution, status="cancelled", completed_at=now, failure_summary="Forced cancellation applied; Agent process may still be running locally."))
            if request.task_execution_id:
                task = self.tasks.get(request.task_execution_id)
                if task is not None and task.status not in TERMINAL_TASK_STATUSES:
                    self.tasks.save(replace(task, status="cancelled", completed_at=now, failure_summary="Forced cancellation applied."))
            self.cancellation_requests.save(replace(request, status="forced", completed_at=now))
            self.outbox.append_event("execution.cancel_forced", "execution", request.execution_id, {"execution_id": request.execution_id, "cancellation_request_id": request.id})
            count += 1
        self.transaction.commit()
        return {"forced": count}


class DetectLostAttempts:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        leases: ExecutionLeaseRepository,
        retry_schedules: RetryScheduleRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.leases = leases
        self.retry_schedules = retry_schedules
        self.reservations = reservations
        self.locks = locks
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, limit: int = 100) -> dict[str, int]:
        now = utcnow()
        lost = 0
        retried = 0
        for lease in self.leases.due_for_expiration(now, limit=limit):
            attempt = self.attempts.get(lease.execution_attempt_id)
            if attempt is None or attempt.status not in ACTIVE_ATTEMPT_STATUSES:
                self.leases.save(replace(lease, status="completed", revoked_at=now, revocation_reason="attempt_already_terminal"))
                continue
            task = _require_task(self.tasks, attempt.task_execution_id)
            execution = _require_execution(self.executions, task.execution_id)
            self.leases.save(replace(lease, status="expired"))
            self.attempts.save(replace(attempt, status="lost", completed_at=now, error_code="LEASE_EXPIRED", error_message="Execution lease expired after grace period."))
            self.reservations.release_for_attempt(attempt.id, now, "attempt_lost")
            self.locks.release_for_attempt(attempt.id, now, "attempt_lost")
            decision = EvaluateRetryPolicy().execute(task, attempt, reason="lost", error_code="LEASE_EXPIRED")
            if decision.get("retry"):
                available_at = now + timedelta(seconds=int(decision["delay_seconds"]))
                self.tasks.save(replace(task, status="ready", available_at=available_at, next_scheduling_attempt_at=available_at, last_scheduling_failure={"code": "ATTEMPT_LOST", "source_attempt_id": attempt.id}))
                self.executions.save(replace(execution, status="pending"))
                self.retry_schedules.add(
                    RetryScheduleDTO(
                        id=new_id("retry"),
                        task_execution_id=task.id,
                        source_attempt_id=attempt.id,
                        attempt_number=attempt.attempt_number + 1,
                        retry_number=attempt.attempt_number,
                        reason="lost",
                        error_code="LEASE_EXPIRED",
                        status="scheduled",
                        available_at=available_at,
                        created_at=now,
                    )
                )
                retried += 1
            else:
                self.tasks.save(replace(task, status="failed", completed_at=now, failure_summary="Attempt lost and retry policy denied a new attempt."))
                self.executions.save(replace(execution, status="failed", completed_at=now, failure_summary="Attempt lost and retry policy denied a new attempt."))
            self.outbox.append_event("execution_attempt.lost", "execution_attempt", attempt.id, {"execution_attempt_id": attempt.id, "lease_id": lease.id, "retry": bool(decision.get("retry"))})
            lost += 1
        self.transaction.commit()
        return {"lost": lost, "retried": retried}


def _current_active_attempt(attempts: list[ExecutionAttemptDTO]) -> ExecutionAttemptDTO | None:
    for attempt in reversed(attempts):
        if attempt.status in ACTIVE_ATTEMPT_STATUSES:
            return attempt
    return None


def _require_execution(executions: ExecutionRepository, execution_id: str) -> ExecutionDTO:
    execution = executions.get(execution_id)
    if execution is None:
        raise ValueError("Execution not found.")
    return execution


def _require_task(tasks: TaskExecutionRepository, task_execution_id: str) -> TaskExecutionDTO:
    task = tasks.get(task_execution_id)
    if task is None:
        raise ValueError("TaskExecution not found.")
    return task


def _require_attempt(attempts: ExecutionAttemptRepository, attempt_id: str) -> ExecutionAttemptDTO:
    attempt = attempts.get(attempt_id)
    if attempt is None:
        raise ValueError("ExecutionAttempt not found.")
    return attempt


def _positive_int(value: Any, default: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return default
    return candidate if candidate > 0 else default


def utcnow() -> datetime:
    return datetime.utcnow()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
