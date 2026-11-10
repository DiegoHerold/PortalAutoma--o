from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.dispatch.application.dto import AgentSyncStateCommand, AgentSyncStateResultDTO, ReconciliationRecordDTO
from modules.dispatch.application.ports import (
    ExecutionLeaseRepository,
    OfferReservationPort,
    OutboxPort,
    ReconciliationRecordRepository,
    ResourceLockRepository,
    TransactionManager,
)
from modules.dispatch.application.use_cases.offers import ReleaseAttemptDispatchResources
from modules.dispatch.domain.states import ReconciliationStatus
from modules.orchestration.application.ports import (
    AutomationVersionReader,
    ExecutionAttemptRepository,
    ExecutionOfferRepository,
    ExecutionRepository,
    TaskExecutionRepository,
)
from modules.orchestration.application.use_cases.executions import (
    HandleExecutionCancelled,
    HandleExecutionCompleted,
    HandleExecutionFailed,
    HandleExecutionStarted,
    HandleExecutionTimedOut,
)


IN_SYNC = "IN_SYNC"
LOCAL_AHEAD = "LOCAL_AHEAD"
REMOTE_AHEAD = "REMOTE_AHEAD"
CONFLICT = "CONFLICT"
REQUIRES_INTERVENTION = "REQUIRES_INTERVENTION"

ACTIVE_ATTEMPT_STATUSES = {"accepted", "committed", "preparing", "running", "cancel_requested"}
PRE_RUNNING_ATTEMPT_STATUSES = {"committed", "preparing"}
TERMINAL_ATTEMPT_STATUSES = {"succeeded", "failed", "cancelled", "timed_out", "lost", "rejected", "expired"}
TERMINAL_EXECUTION_STATUSES = {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out"}
ACTIVE_AGENT_STATES = {"reserved", "committed", "preparing", "starting", "running", "finalizing", "cancel_requested", "cancelling"}
TERMINAL_AGENT_STATES = {"succeeded", "failed", "cancelled", "timed_out", "lost", "rejected"}


class ReconcileAgentSyncState:
    """Reconcilia o retrato local do Agent com a verdade persistente do Portal."""

    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        leases: ExecutionLeaseRepository,
        automation_versions: AutomationVersionReader,
        reconciliations: ReconciliationRecordRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.offers = offers
        self.reservations = reservations
        self.locks = locks
        self.leases = leases
        self.automation_versions = automation_versions
        self.reconciliations = reconciliations
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, command: AgentSyncStateCommand) -> AgentSyncStateResultDTO:
        payload = command.payload
        self._validate_sender(command)
        now = utcnow()
        summary = {IN_SYNC: 0, LOCAL_AHEAD: 0, REMOTE_AHEAD: 0, CONFLICT: 0, REQUIRES_INTERVENTION: 0}
        decisions: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []

        for item in _list(payload.get("running_executions")):
            decision = self._reconcile_execution(command.agent_id, command.agent_instance_id, item, now)
            decisions.append(decision)
            summary[decision["decision"]] += 1
            if decision.get("action"):
                actions.append(decision["action"])
            self._record("agent.sync_state.execution", command, decision, now)

        lease_summary = self._reconcile_leases(command, now)
        reservation_summary = self._reconcile_reservations(command, now)
        artifact_summary = self._artifact_summary(payload)

        self.outbox.append_event(
            "agent.sync_state.reconciled",
            "agent",
            command.agent_id,
            {
                "agent_id": command.agent_id,
                "agent_instance_id": command.agent_instance_id,
                "summary": summary,
                "actions": actions,
                "lease_summary": lease_summary,
                "reservation_summary": reservation_summary,
                "artifact_summary": artifact_summary,
            },
        )
        self.transaction.commit()
        return AgentSyncStateResultDTO(
            agent_id=command.agent_id,
            agent_instance_id=command.agent_instance_id,
            reason=payload.get("reason") if isinstance(payload.get("reason"), str) else None,
            summary=summary,
            decisions=decisions,
            actions=actions,
            reservations=reservation_summary,
            leases=lease_summary,
            artifacts=artifact_summary,
            recorded_at=now,
        )

    def _validate_sender(self, command: AgentSyncStateCommand) -> None:
        payload_agent = command.payload.get("agent_id")
        payload_instance = command.payload.get("agent_instance_id") or command.payload.get("instance_id")
        if payload_agent not in (None, "", command.agent_id):
            raise ValueError("agent.sync_state payload Agent differs from the authenticated Agent.")
        if payload_instance not in (None, "", command.agent_instance_id):
            raise ValueError("agent.sync_state payload AgentInstance differs from the active connection.")

    def _reconcile_execution(self, agent_id: str, agent_instance_id: str, item: dict[str, Any], now: datetime) -> dict[str, Any]:
        execution_id = _string(item.get("execution_id"))
        attempt_id = _string(item.get("execution_attempt_id"))
        agent_state_raw = _string(item.get("state"))
        agent_state = _normalize_agent_state(agent_state_raw)

        base = {
            "execution_id": execution_id,
            "execution_attempt_id": attempt_id,
            "agent_state": agent_state_raw,
            "normalized_agent_state": agent_state,
        }
        if agent_state is None:
            return {**base, "decision": REQUIRES_INTERVENTION, "reason": "UNKNOWN_AGENT_STATE"}

        attempt = self._resolve_attempt(execution_id, attempt_id)
        if attempt is None:
            return {**base, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_ATTEMPT_NOT_FOUND"}

        if attempt.agent_id != agent_id or attempt.agent_instance_id != agent_instance_id:
            return {
                **base,
                "execution_attempt_id": attempt.id,
                "decision": REQUIRES_INTERVENTION,
                "reason": "ATTEMPT_AGENT_MISMATCH",
                "portal_agent_id": attempt.agent_id,
                "portal_agent_instance_id": attempt.agent_instance_id,
            }

        task = self.tasks.get(attempt.task_execution_id)
        if task is None:
            return {**base, "execution_attempt_id": attempt.id, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_TASK_NOT_FOUND"}
        execution = self.executions.get(task.execution_id)
        if execution is None:
            return {**base, "execution_attempt_id": attempt.id, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_EXECUTION_NOT_FOUND"}
        if execution_id and execution_id != execution.id:
            return {
                **base,
                "execution_attempt_id": attempt.id,
                "portal_execution_id": execution.id,
                "decision": REQUIRES_INTERVENTION,
                "reason": "EXECUTION_ID_MISMATCH",
            }

        base = {
            **base,
            "execution_id": execution.id,
            "execution_attempt_id": attempt.id,
            "portal_attempt_status": attempt.status,
            "portal_task_status": task.status,
            "portal_execution_status": execution.status,
        }

        if agent_state in ACTIVE_AGENT_STATES:
            if attempt.status == "cancel_requested" or execution.status == "cancelling":
                return {
                    **base,
                    "decision": REMOTE_AHEAD,
                    "reason": "PORTAL_CANCEL_REQUESTED",
                    "action": {
                        "type": "cancel",
                        "execution_id": execution.id,
                        "execution_attempt_id": attempt.id,
                        "reason": "portal_cancel_requested",
                    },
                }
            if attempt.status in TERMINAL_ATTEMPT_STATUSES or execution.status in TERMINAL_EXECUTION_STATUSES:
                return {**base, "decision": CONFLICT, "reason": "PORTAL_TERMINAL_AGENT_ACTIVE"}
            if attempt.status in ACTIVE_ATTEMPT_STATUSES:
                return {**base, "decision": IN_SYNC, "reason": "ACTIVE_COMPATIBLE"}
            return {**base, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_ATTEMPT_NOT_ACTIVE"}

        if agent_state in TERMINAL_AGENT_STATES:
            expected_execution_status = "succeeded" if agent_state == "succeeded" else agent_state
            if attempt.status in TERMINAL_ATTEMPT_STATUSES or execution.status in TERMINAL_EXECUTION_STATUSES:
                if attempt.status == expected_execution_status and execution.status == expected_execution_status:
                    return {**base, "decision": IN_SYNC, "reason": "TERMINAL_COMPATIBLE"}
                return {**base, "decision": CONFLICT, "reason": "TERMINAL_STATUS_DIVERGED"}
            if attempt.status in ACTIVE_ATTEMPT_STATUSES:
                if attempt.status == "cancel_requested" and agent_state == "succeeded":
                    return {**base, "decision": CONFLICT, "reason": "PORTAL_CANCEL_REQUESTED_AGENT_SUCCEEDED"}
                applied = self._apply_local_ahead_terminal(agent_state, attempt.id, agent_id, agent_instance_id, item, now)
                return {**base, "decision": LOCAL_AHEAD, "reason": "AGENT_TERMINAL_APPLIED", "applied_status": applied}
            return {**base, "decision": REQUIRES_INTERVENTION, "reason": "AGENT_TERMINAL_FROM_UNCOMMITTED_ATTEMPT"}

        return {**base, "decision": REQUIRES_INTERVENTION, "reason": "UNHANDLED_AGENT_STATE"}

    def _resolve_attempt(self, execution_id: str | None, attempt_id: str | None):
        if attempt_id:
            return self.attempts.get(attempt_id)
        if execution_id:
            attempts = self.attempts.list_for_execution(execution_id)
            return attempts[-1] if attempts else None
        return None

    def _apply_local_ahead_terminal(self, agent_state: str, attempt_id: str, agent_id: str, agent_instance_id: str, item: dict[str, Any], now: datetime) -> str:
        attempt = self.attempts.get(attempt_id)
        if attempt is None:
            raise ValueError("ExecutionAttempt disappeared during reconciliation.")
        if attempt.status in PRE_RUNNING_ATTEMPT_STATUSES:
            HandleExecutionStarted(
                self.executions,
                self.tasks,
                self.attempts,
                self.offers,
                self.reservations,
                self.outbox,
                self.transaction,
            ).execute(
                attempt_id=attempt_id,
                offer_id=attempt.offer_id,
                agent_id=agent_id,
                agent_instance_id=agent_instance_id,
                started_at=item.get("started_at") or item.get("observed_at") or now.isoformat(),
            )

        handler_map = {
            "succeeded": (HandleExecutionCompleted, "completed_at"),
            "failed": (HandleExecutionFailed, "failed_at"),
            "cancelled": (HandleExecutionCancelled, "cancelled_at"),
            "timed_out": (HandleExecutionTimedOut, "timed_out_at"),
        }
        handler_entry = handler_map.get(agent_state)
        if handler_entry is None:
            raise ValueError(f"Cannot apply terminal sync state {agent_state}.")
        handler_class, timestamp_field = handler_entry
        payload = {
            "execution_attempt_id": attempt_id,
            "occurred_at": item.get("occurred_at") or item.get(timestamp_field) or now.isoformat(),
            timestamp_field: item.get(timestamp_field) or item.get("completed_at") or now.isoformat(),
            "output": item.get("output") if isinstance(item.get("output"), dict) else {},
            "result": item.get("result") if isinstance(item.get("result"), dict) else {"source": "agent.sync_state"},
            "exit_code": _int_or_none(item.get("exit_code")),
            "resource_usage": item.get("resource_usage") if isinstance(item.get("resource_usage"), dict) else None,
            "code": item.get("code") or item.get("error_code"),
            "error_message": item.get("error_message") or item.get("message"),
        }
        details = handler_class(
            self.executions,
            self.tasks,
            self.attempts,
            self.offers,
            self.reservations,
            self.automation_versions,
            self.outbox,
            self.transaction,
        ).execute(attempt_id=attempt_id, agent_id=agent_id, agent_instance_id=agent_instance_id, payload=payload)
        ReleaseAttemptDispatchResources(self.reservations, self.locks, self.leases, self.outbox, self.transaction).execute(attempt_id, "agent.sync_state.local_ahead")
        return details.current_attempt.status if details.current_attempt else details.execution.status

    def _reconcile_leases(self, command: AgentSyncStateCommand, now: datetime) -> dict[str, Any]:
        total = 0
        in_sync = 0
        missing = 0
        conflicts = 0
        for item in _list(command.payload.get("leases")):
            total += 1
            lease_id = _string(item.get("lease_id"))
            attempt_id = _string(item.get("execution_attempt_id"))
            state = _string(item.get("state"))
            details = {"lease_id": lease_id, "execution_attempt_id": attempt_id, "agent_state": state}
            if not lease_id:
                missing += 1
                self._record("agent.sync_state.lease", command, {**details, "decision": REQUIRES_INTERVENTION, "reason": "MISSING_LEASE_ID"}, now)
                continue
            lease = self.leases.get(lease_id)
            if lease is None:
                missing += 1
                self._record("agent.sync_state.lease", command, {**details, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_LEASE_NOT_FOUND"}, now)
                continue
            if attempt_id and lease.execution_attempt_id != attempt_id:
                conflicts += 1
                self._record(
                    "agent.sync_state.lease",
                    command,
                    {**details, "decision": CONFLICT, "reason": "LEASE_ATTEMPT_MISMATCH", "portal_attempt_id": lease.execution_attempt_id},
                    now,
                )
                continue
            in_sync += 1
            self._record("agent.sync_state.lease", command, {**details, "decision": IN_SYNC, "portal_status": lease.status}, now)
        return {"reported": total, "in_sync": in_sync, "missing": missing, "conflicts": conflicts}

    def _reconcile_reservations(self, command: AgentSyncStateCommand, now: datetime) -> dict[str, Any]:
        total = 0
        in_sync = 0
        missing = 0
        for item in _list(command.payload.get("reservations")):
            total += 1
            reservation_id = _string(item.get("reservation_id"))
            attempt_id = _string(item.get("execution_attempt_id"))
            details = {"reservation_id": reservation_id, "execution_attempt_id": attempt_id, "agent_status": _string(item.get("status"))}
            if not reservation_id or not attempt_id:
                missing += 1
                self._record("agent.sync_state.reservation", command, {**details, "decision": REQUIRES_INTERVENTION, "reason": "MISSING_RESERVATION_CORRELATION"}, now)
                continue
            portal_reservations = self.reservations.list_for_attempt(attempt_id)
            if any(reservation.id == reservation_id for reservation in portal_reservations):
                in_sync += 1
                self._record("agent.sync_state.reservation", command, {**details, "decision": IN_SYNC}, now)
            else:
                missing += 1
                self._record("agent.sync_state.reservation", command, {**details, "decision": REQUIRES_INTERVENTION, "reason": "PORTAL_RESERVATION_NOT_FOUND"}, now)
        return {"reported": total, "in_sync": in_sync, "missing": missing}

    def _artifact_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        pending = _list(payload.get("pending_artifacts"))
        return {
            "reported_pending": len(pending),
            "integration": "BLOCKED_FOR_PROMPT_2" if pending else "NO_PENDING_ARTIFACTS_REPORTED",
            "contract": "artifact.created -> upload_url -> artifact.uploaded; Agent-side durable upload confirmation remains out of Prompt 1.",
        }

    def _record(self, kind: str, command: AgentSyncStateCommand, decision: dict[str, Any], now: datetime) -> None:
        status = ReconciliationStatus.RECORDED.value
        if decision.get("decision") == LOCAL_AHEAD and decision.get("applied_status"):
            status = ReconciliationStatus.APPLIED.value
        elif decision.get("decision") in {CONFLICT, REQUIRES_INTERVENTION}:
            status = ReconciliationStatus.NEEDS_ATTENTION.value
        record = ReconciliationRecordDTO(
            id=f"rec_{uuid4().hex}",
            kind=kind,
            status=status,
            decision=str(decision.get("decision") or REQUIRES_INTERVENTION),
            details=_json_safe(decision),
            created_at=now,
            completed_at=now if status == ReconciliationStatus.APPLIED.value else None,
            agent_id=command.agent_id,
            agent_instance_id=command.agent_instance_id,
            execution_attempt_id=_string(decision.get("execution_attempt_id")),
        )
        self.reconciliations.add(record)


def _normalize_agent_state(value: str | None) -> str | None:
    if not value:
        return None
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value).replace("-", "_").replace(" ", "_").lower()
    aliases = {
        "success": "succeeded",
        "completed": "succeeded",
        "complete": "succeeded",
        "canceled": "cancelled",
        "cancel_requested": "cancel_requested",
        "cancellation_requested": "cancel_requested",
        "cancelling": "cancelling",
        "canceling": "cancelling",
        "timedout": "timed_out",
        "timeout": "timed_out",
        "timed_out": "timed_out",
        "orphaned": "lost",
        "interrupted": "lost",
    }
    return aliases.get(snake, snake)


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_safe(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return _json_safe(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if key not in {"workspace_path"}}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def utcnow() -> datetime:
    return datetime.now(UTC)
