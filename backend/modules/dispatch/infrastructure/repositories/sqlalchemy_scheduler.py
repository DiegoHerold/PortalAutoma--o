from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from modules.dispatch.application.dto import (
    AgentDispatchSnapshotDTO,
    CancellationRequestDTO,
    DispatchDecisionDTO,
    ExecutionLeaseDTO,
    ReconciliationRecordDTO,
    ResourceLockDTO,
    RetryScheduleDTO,
)
from modules.dispatch.infrastructure.orm.models import (
    CancellationRequestRecord,
    DispatchDecisionRecord,
    ExecutionLeaseRecord,
    ReconciliationRecord,
    ResourceLockRecord,
    RetryScheduleRecord,
)
from modules.fleet.infrastructure.orm.models import (
    AgentCapabilityRecord,
    AgentInstanceRecord,
    AgentMachineProfileRecord,
    AgentPoolRecord,
    AgentRecord,
    AgentResourceSnapshotRecord,
    InteractiveSessionSnapshotRecord,
)
from modules.orchestration.application.dto import TaskExecutionDTO
from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord, TaskExecutionRecord


ACTIVE_ATTEMPT_STATUSES = {"offered", "accepted", "committed", "preparing", "running", "cancel_requested"}


class SqlAlchemyReadyTaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def claim_ready(self, now: datetime, limit: int) -> list[TaskExecutionDTO]:
        active_attempt = (
            select(ExecutionAttemptRecord.id)
            .where(
                ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id,
                ExecutionAttemptRecord.status.in_(ACTIVE_ATTEMPT_STATUSES),
            )
            .exists()
        )
        rows = self.db.scalars(
            select(TaskExecutionRecord)
            .where(
                TaskExecutionRecord.status.in_(["ready", "queued"]),
                or_(TaskExecutionRecord.available_at.is_(None), TaskExecutionRecord.available_at <= now),
                or_(TaskExecutionRecord.next_scheduling_attempt_at.is_(None), TaskExecutionRecord.next_scheduling_attempt_at <= now),
                ~active_attempt,
            )
            .order_by(TaskExecutionRecord.priority.desc(), TaskExecutionRecord.ready_at.asc().nullslast(), TaskExecutionRecord.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_task_to_dto(row) for row in rows]

    def get(self, task_execution_id: str) -> TaskExecutionDTO | None:
        # Locks the row (blocking, no skip_locked) so this single-task dispatch
        # path - used by the synchronous POST /executions flow - can never run
        # concurrently with the Celery beat "schedule_ready_tasks" poller's
        # claim_ready() (which locks the same row via FOR UPDATE SKIP LOCKED
        # every 5s). Without this, both paths could grab the same freshly-ready
        # task at once and race to insert execution_attempts for it, which
        # Postgres resolves as a deadlock instead of a simple wait - leaving the
        # execution stuck in "pending" forever once the loser's transaction is
        # rolled back.
        row = self.db.get(TaskExecutionRecord, task_execution_id, with_for_update=True)
        return _task_to_dto(row) if row else None

    def save(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        row = self.db.get(TaskExecutionRecord, task.id)
        if row is None:
            row = TaskExecutionRecord(**task.__dict__)
        else:
            for key, value in task.__dict__.items():
                setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _task_to_dto(row)


class SqlAlchemyDispatchCandidateReader:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_candidates(self, preferred_agent_id: str | None = None) -> list[AgentDispatchSnapshotDTO]:
        query = select(AgentRecord).order_by(AgentRecord.id)
        if preferred_agent_id:
            query = query.where(or_(AgentRecord.id == preferred_agent_id, AgentRecord.id != preferred_agent_id)).order_by((AgentRecord.id != preferred_agent_id).asc(), AgentRecord.id.asc())
        rows = self.db.scalars(query).all()
        return [self._candidate(row) for row in rows]

    def active_attempt_count(self, agent_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(ExecutionAttemptRecord.id)).where(
                    ExecutionAttemptRecord.agent_id == agent_id,
                    ExecutionAttemptRecord.status.in_(ACTIVE_ATTEMPT_STATUSES),
                )
            )
            or 0
        )

    def _candidate(self, agent: AgentRecord) -> AgentDispatchSnapshotDTO:
        instance = self.db.scalar(
            select(AgentInstanceRecord)
            .where(AgentInstanceRecord.agent_id == agent.id, AgentInstanceRecord.disconnected_at.is_(None))
            .order_by(AgentInstanceRecord.connected_at.desc().nullslast(), AgentInstanceRecord.created_at.desc())
            .limit(1)
        )
        snapshot = self.db.scalar(
            select(AgentResourceSnapshotRecord)
            .where(AgentResourceSnapshotRecord.agent_id == agent.id)
            .order_by(AgentResourceSnapshotRecord.observed_at.desc())
            .limit(1)
        )
        profile = self.db.scalar(
            select(AgentMachineProfileRecord)
            .where(AgentMachineProfileRecord.agent_id == agent.id)
            .order_by(AgentMachineProfileRecord.observed_at.desc())
            .limit(1)
        )
        session = self.db.scalar(
            select(InteractiveSessionSnapshotRecord)
            .where(InteractiveSessionSnapshotRecord.agent_id == agent.id)
            .order_by(InteractiveSessionSnapshotRecord.observed_at.desc())
            .limit(1)
        )
        capabilities = self.db.scalars(
            select(AgentCapabilityRecord).where(AgentCapabilityRecord.agent_id == agent.id, AgentCapabilityRecord.is_current.is_(True))
        ).all()
        pools = self.db.scalars(
            select(AgentPoolRecord).where(AgentPoolRecord.agent_id == agent.id, AgentPoolRecord.is_current.is_(True))
        ).all()
        return AgentDispatchSnapshotDTO(
            agent_id=agent.id,
            agent_instance_id=instance.id if instance else None,
            worker_id=agent.worker_id,
            enabled=agent.enabled,
            connectivity_status=agent.connectivity_status,
            administrative_status=agent.administrative_status,
            health_status=agent.health_status,
            occupancy_status=agent.occupancy_status,
            protocol_version=(instance.negotiated_protocol_version if instance else None) or agent.protocol_version,
            agent_version=(instance.agent_version if instance else None) or agent.current_version,
            last_seen_at=agent.last_seen_at,
            snapshot_observed_at=snapshot.observed_at if snapshot else None,
            snapshot_expires_at=snapshot.expires_at if snapshot else None,
            snapshot_revision=snapshot.revision if snapshot else None,
            cpu_usage_percentage=snapshot.cpu_usage_percentage if snapshot else None,
            memory_available_mb=snapshot.memory_available_mb if snapshot else None,
            disk_free_mb=snapshot.disk_free_mb if snapshot else None,
            machine_profile=_profile_payload(profile),
            capabilities=[_capability_payload(item) for item in capabilities],
            pools={pool.pool_type: _pool_payload(pool) for pool in pools},
            interactive_session=_session_payload(session),
            active_attempts=self.active_attempt_count(agent.id),
        )


class SqlAlchemyDispatchDecisionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, decision: DispatchDecisionDTO) -> DispatchDecisionDTO:
        row = DispatchDecisionRecord(
            id=decision.id,
            scheduler_run_id=decision.scheduler_run_id,
            task_execution_id=decision.task_execution_id,
            execution_attempt_id=decision.execution_attempt_id,
            execution_offer_id=decision.execution_offer_id,
            selected_agent_id=decision.selected_agent_id,
            selected_agent_instance_id=decision.selected_agent_instance_id,
            status=decision.status,
            decision_reason=decision.decision_reason,
            candidates=decision.candidates,
            weights=decision.weights,
            metadata_json=decision.metadata,
            created_at=decision.created_at,
        )
        self.db.add(row)
        self.db.flush()
        return _decision_to_dto(row)

    def get(self, decision_id: str) -> DispatchDecisionDTO | None:
        row = self.db.get(DispatchDecisionRecord, decision_id)
        return _decision_to_dto(row) if row else None

    def list_for_task(self, task_execution_id: str) -> list[DispatchDecisionDTO]:
        rows = self.db.scalars(
            select(DispatchDecisionRecord)
            .where(DispatchDecisionRecord.task_execution_id == task_execution_id)
            .order_by(DispatchDecisionRecord.created_at.desc())
        ).all()
        return [_decision_to_dto(row) for row in rows]

    def list_for_execution(self, execution_id: str) -> list[DispatchDecisionDTO]:
        rows = self.db.scalars(
            select(DispatchDecisionRecord)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == DispatchDecisionRecord.task_execution_id)
            .where(TaskExecutionRecord.execution_id == execution_id)
            .order_by(DispatchDecisionRecord.created_at.desc())
        ).all()
        return [_decision_to_dto(row) for row in rows]


class SqlAlchemyResourceLockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, lock: ResourceLockDTO) -> ResourceLockDTO:
        row = ResourceLockRecord(**_lock_dict(lock))
        self.db.add(row)
        self.db.flush()
        return _lock_to_dto(row)

    def save(self, lock: ResourceLockDTO) -> ResourceLockDTO:
        row = self.db.get(ResourceLockRecord, lock.id)
        if row is None:
            return self.add(lock)
        for key, value in _lock_dict(lock).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _lock_to_dto(row)

    def active_conflict(self, normalized_key: str, scope: str) -> ResourceLockDTO | None:
        row = self.db.scalar(
            select(ResourceLockRecord)
            .where(ResourceLockRecord.normalized_key == normalized_key, ResourceLockRecord.scope == scope, ResourceLockRecord.status == "active")
            .with_for_update(skip_locked=True)
        )
        return _lock_to_dto(row) if row else None

    def list_for_attempt(self, execution_attempt_id: str) -> list[ResourceLockDTO]:
        rows = self.db.scalars(select(ResourceLockRecord).where(ResourceLockRecord.execution_attempt_id == execution_attempt_id).order_by(ResourceLockRecord.acquired_at)).all()
        return [_lock_to_dto(row) for row in rows]

    def release_for_attempt(self, execution_attempt_id: str, now: datetime, reason: str) -> None:
        rows = self.db.scalars(
            select(ResourceLockRecord)
            .where(ResourceLockRecord.execution_attempt_id == execution_attempt_id, ResourceLockRecord.status == "active")
            .with_for_update()
        ).all()
        for row in rows:
            row.status = "released"
            row.released_at = now
            row.release_reason = reason
            self.db.add(row)
        self.db.flush()

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ResourceLockDTO]:
        rows = self.db.scalars(
            select(ResourceLockRecord)
            .where(ResourceLockRecord.status == "active", ResourceLockRecord.expires_at <= now)
            .order_by(ResourceLockRecord.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_lock_to_dto(row) for row in rows]


class SqlAlchemyExecutionLeaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, lease: ExecutionLeaseDTO) -> ExecutionLeaseDTO:
        row = ExecutionLeaseRecord(**lease.__dict__)
        self.db.add(row)
        self.db.flush()
        return _lease_to_dto(row)

    def save(self, lease: ExecutionLeaseDTO) -> ExecutionLeaseDTO:
        row = self.db.get(ExecutionLeaseRecord, lease.id)
        if row is None:
            return self.add(lease)
        for key, value in lease.__dict__.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _lease_to_dto(row)

    def get(self, lease_id: str) -> ExecutionLeaseDTO | None:
        row = self.db.get(ExecutionLeaseRecord, lease_id)
        return _lease_to_dto(row) if row else None

    def active_for_attempt(self, execution_attempt_id: str) -> ExecutionLeaseDTO | None:
        row = self.db.scalar(
            select(ExecutionLeaseRecord)
            .where(ExecutionLeaseRecord.execution_attempt_id == execution_attempt_id, ExecutionLeaseRecord.status.in_(["active", "suspect"]))
            .order_by(ExecutionLeaseRecord.issued_at.desc())
            .limit(1)
            .with_for_update()
        )
        return _lease_to_dto(row) if row else None

    def due_for_suspect(self, now: datetime, limit: int = 100) -> list[ExecutionLeaseDTO]:
        rows = self.db.scalars(
            select(ExecutionLeaseRecord)
            .where(ExecutionLeaseRecord.status == "active", ExecutionLeaseRecord.expires_at <= now)
            .order_by(ExecutionLeaseRecord.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_lease_to_dto(row) for row in rows]

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ExecutionLeaseDTO]:
        rows = self.db.scalars(
            select(ExecutionLeaseRecord)
            .where(ExecutionLeaseRecord.status.in_(["suspect", "expired"]), ExecutionLeaseRecord.grace_until <= now)
            .order_by(ExecutionLeaseRecord.grace_until)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_lease_to_dto(row) for row in rows]


class SqlAlchemyRetryScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, schedule: RetryScheduleDTO) -> RetryScheduleDTO:
        row = RetryScheduleRecord(**schedule.__dict__)
        self.db.add(row)
        self.db.flush()
        return _retry_to_dto(row)

    def save(self, schedule: RetryScheduleDTO) -> RetryScheduleDTO:
        row = self.db.get(RetryScheduleRecord, schedule.id)
        if row is None:
            return self.add(schedule)
        for key, value in schedule.__dict__.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _retry_to_dto(row)

    def due(self, now: datetime, limit: int = 100) -> list[RetryScheduleDTO]:
        rows = self.db.scalars(
            select(RetryScheduleRecord)
            .where(RetryScheduleRecord.status == "scheduled", RetryScheduleRecord.available_at <= now)
            .order_by(RetryScheduleRecord.available_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_retry_to_dto(row) for row in rows]


class SqlAlchemyCancellationRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, request: CancellationRequestDTO) -> CancellationRequestDTO:
        row = CancellationRequestRecord(**request.__dict__)
        self.db.add(row)
        self.db.flush()
        return _cancel_to_dto(row)

    def save(self, request: CancellationRequestDTO) -> CancellationRequestDTO:
        row = self.db.get(CancellationRequestRecord, request.id)
        if row is None:
            return self.add(request)
        for key, value in request.__dict__.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _cancel_to_dto(row)

    def current_for_execution(self, execution_id: str) -> CancellationRequestDTO | None:
        row = self.db.scalar(
            select(CancellationRequestRecord)
            .where(CancellationRequestRecord.execution_id == execution_id, CancellationRequestRecord.status.in_(["requested", "command_sent", "force_required"]))
            .order_by(CancellationRequestRecord.requested_at.desc())
            .limit(1)
            .with_for_update()
        )
        return _cancel_to_dto(row) if row else None

    def due_for_force(self, now: datetime, limit: int = 100) -> list[CancellationRequestDTO]:
        rows = self.db.scalars(
            select(CancellationRequestRecord)
            .where(CancellationRequestRecord.status == "command_sent", CancellationRequestRecord.force_after <= now)
            .order_by(CancellationRequestRecord.force_after)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_cancel_to_dto(row) for row in rows]


class SqlAlchemyReconciliationRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, record: ReconciliationRecordDTO) -> ReconciliationRecordDTO:
        row = ReconciliationRecord(**record.__dict__)
        self.db.add(row)
        self.db.flush()
        return _reconciliation_to_dto(row)


def _task_to_dto(row: TaskExecutionRecord) -> TaskExecutionDTO:
    return TaskExecutionDTO(
        id=row.id,
        execution_id=row.execution_id,
        automation_version_id=row.automation_version_id,
        status=row.status,
        priority=row.priority,
        parameters=row.parameters or {},
        input=row.input or {},
        result=row.result,
        retry_policy=row.retry_policy or {},
        timeout_policy=row.timeout_policy or {},
        created_at=row.created_at,
        ready_at=row.ready_at,
        queued_at=row.queued_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        current_attempt_number=row.current_attempt_number,
        failure_summary=row.failure_summary,
        requirements_snapshot=row.requirements_snapshot or {},
        available_at=row.available_at,
        scheduling_attempts=row.scheduling_attempts or 0,
        last_scheduling_attempt_at=row.last_scheduling_attempt_at,
        next_scheduling_attempt_at=row.next_scheduling_attempt_at,
        last_scheduling_failure=row.last_scheduling_failure,
    )


def _profile_payload(row: AgentMachineProfileRecord | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "operating_system": row.operating_system,
        "architecture": row.architecture,
        "total_memory_mb": row.total_memory_mb,
        "interactive_session_supported": row.interactive_session_supported,
        "revision": row.revision,
        "observed_at": row.observed_at,
        "expires_at": row.expires_at,
    }


def _capability_payload(row: AgentCapabilityRecord) -> dict[str, Any]:
    return {
        "key": row.key,
        "status": row.status,
        "version": row.version,
        "attributes": row.attributes_json or {},
        "observed_at": row.observed_at,
        "expires_at": row.expires_at,
        "revision": row.revision,
    }


def _pool_payload(row: AgentPoolRecord) -> dict[str, Any]:
    return {
        "recommended_total": row.recommended_total,
        "administrator_total": row.administrator_total,
        "effective_total": row.effective_total,
        "used": row.used,
        "reserved": row.reserved,
        "available": row.available,
        "observed_at": row.observed_at,
        "revision": row.revision,
    }


def _session_payload(row: InteractiveSessionSnapshotRecord | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "available": row.available,
        "locked": row.locked,
        "state": row.state,
        "observed_at": row.observed_at,
        "expires_at": row.expires_at,
    }


def _decision_to_dto(row: DispatchDecisionRecord) -> DispatchDecisionDTO:
    return DispatchDecisionDTO(
        id=row.id,
        scheduler_run_id=row.scheduler_run_id,
        task_execution_id=row.task_execution_id,
        execution_attempt_id=row.execution_attempt_id,
        execution_offer_id=row.execution_offer_id,
        selected_agent_id=row.selected_agent_id,
        selected_agent_instance_id=row.selected_agent_instance_id,
        status=row.status,
        decision_reason=row.decision_reason,
        candidates=row.candidates or [],
        weights=row.weights or {},
        metadata=row.metadata_json or {},
        created_at=row.created_at,
    )


def _lock_dict(lock: ResourceLockDTO) -> dict[str, Any]:
    return lock.__dict__.copy()


def _lock_to_dto(row: ResourceLockRecord) -> ResourceLockDTO:
    return ResourceLockDTO(
        id=row.id,
        resource_key=row.resource_key,
        normalized_key=row.normalized_key,
        scope=row.scope,
        agent_id=row.agent_id,
        execution_attempt_id=row.execution_attempt_id,
        status=row.status,
        acquired_at=row.acquired_at,
        expires_at=row.expires_at,
        released_at=row.released_at,
        release_reason=row.release_reason,
    )


def _lease_to_dto(row: ExecutionLeaseRecord) -> ExecutionLeaseDTO:
    return ExecutionLeaseDTO(**{key: getattr(row, key) for key in ExecutionLeaseDTO.__dataclass_fields__})


def _retry_to_dto(row: RetryScheduleRecord) -> RetryScheduleDTO:
    return RetryScheduleDTO(**{key: getattr(row, key) for key in RetryScheduleDTO.__dataclass_fields__})


def _cancel_to_dto(row: CancellationRequestRecord) -> CancellationRequestDTO:
    return CancellationRequestDTO(**{key: getattr(row, key) for key in CancellationRequestDTO.__dataclass_fields__})


def _reconciliation_to_dto(row: ReconciliationRecord) -> ReconciliationRecordDTO:
    return ReconciliationRecordDTO(**{key: getattr(row, key) for key in ReconciliationRecordDTO.__dataclass_fields__})
