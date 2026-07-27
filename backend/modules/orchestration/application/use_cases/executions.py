from __future__ import annotations

import hashlib
import secrets
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from modules.dispatch.domain.offer import ExecutionOffer, RejectionCode
from modules.dispatch.domain.reservation import ResourceReservation
from modules.dispatch.domain.states import ExecutionOfferStatus
from modules.orchestration.application.dto import (
    AgentSelectionRequestDTO,
    CreateAutomationExecutionCommand,
    ExecutionAttemptDTO,
    ExecutionDTO,
    ExecutionDetailsDTO,
    ExecutionOfferDTO,
    ResourceReservationDTO,
    TaskExecutionDTO,
)
from modules.orchestration.application.ports import (
    AgentCommandPort,
    AgentSelectionPort,
    AutomationVersionReader,
    ExecutionAttemptRepository,
    ExecutionOfferRepository,
    ExecutionRepository,
    OfferReservationPort,
    OutboxPort,
    TaskExecutionRepository,
    TransactionManager,
)
from modules.orchestration.domain.errors import (
    AutomationVersionNotExecutable,
    ExecutionNotFound,
    ExecutionSecurityError,
    IdempotencyConflict,
)
from modules.orchestration.domain.execution import Execution
from modules.orchestration.domain.execution_attempt import ExecutionAttempt
from modules.orchestration.domain.policies import calculate_execution_status, calculate_task_execution_status
from modules.orchestration.domain.states import ExecutionAttemptStatus, ExecutionOrigin, ExecutionStatus, ExecutionType, TaskExecutionStatus
from modules.orchestration.domain.task_execution import TaskExecution
from modules.shared.application.idempotency import IdempotencyRecord, IdempotencyReplayStatus
from modules.governance.domain.audit import AuditEvent


class CreateAutomationExecution:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        automation_versions: AutomationVersionReader,
        agent_selection: AgentSelectionPort,
        commands: AgentCommandPort,
        outbox: OutboxPort,
        audit_repo,
        idempotency,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.offers = offers
        self.automation_versions = automation_versions
        self.agent_selection = agent_selection
        self.commands = commands
        self.outbox = outbox
        self.audit = audit_repo
        self.idempotency = idempotency
        self.transaction = transaction

    def execute(self, command: CreateAutomationExecutionCommand) -> ExecutionDetailsDTO:
        try:
            self._reserve_idempotency(command)
        except _IdempotencyReplay as replay:
            return GetExecutionDetails(
                self.executions,
                self.tasks,
                self.attempts,
                self.offers,
                self.automation_versions,
                self.agent_selection,
            ).execute(replay.resource_id)
        version = self.automation_versions.get_published_snapshot(command.automation_version_id)
        if version is None:
            self.transaction.rollback()
            raise AutomationVersionNotExecutable("AutomationVersion must exist, be published, and have published package/runtime.")
        if len(str(command.parameters).encode("utf-8")) > 64 * 1024:
            self.transaction.rollback()
            raise ValueError("Execution parameters payload is too large.")

        now = utcnow()
        execution = Execution.create(
            id=new_id("exe"),
            origin=ExecutionOrigin(command.origin),
            requested_by=command.actor.actor_id,
            organization_id=command.organization_id,
            input={"automation_version_id": version.automation_version_id, "parameters": command.parameters},
            correlation_id=command.correlation_id,
            idempotency_key=command.idempotency_key,
            now=now,
        ).mark_pending()
        execution_dto = self.executions.add(_execution_to_dto(execution))

        task = TaskExecution.create(
            id=new_id("task"),
            execution_id=execution.id,
            automation_version_id=version.automation_version_id,
            priority=command.priority,
            parameters=command.parameters,
            input={"parameters": command.parameters},
            timeout_seconds=version.timeout_seconds,
            now=now,
        ).mark_ready(now).mark_queued(now)
        task_dto = self.tasks.add(_task_to_dto(task))

        selection = self.agent_selection.select(
            AgentSelectionRequestDTO(
                automation_version=version,
                preferred_agent_id=command.agent_id,
                execution_mode=version.execution_mode,
                required_capabilities=version.required_capabilities,
                required_pools=version.required_pools,
            )
        )

        attempt_number = self.attempts.next_attempt_number(task.id)
        attempt = ExecutionAttempt.create(
            id=new_id("att"),
            task_execution_id=task.id,
            attempt_number=attempt_number,
            agent_id=selection.agent_id,
            agent_instance_id=selection.agent_instance_id,
            runtime_version_id=version.runtime_version_id,
            package_id=version.package_id,
            now=now,
        )
        offer_expires_at = now + timedelta(seconds=60)
        offer = ExecutionOffer.create(
            id=new_id("off"),
            execution_attempt_id=attempt.id,
            agent_id=selection.agent_id,
            agent_instance_id=selection.agent_instance_id,
            requirements_snapshot={
                "automation_version_id": version.automation_version_id,
                "execution_id": execution.id,
                "task_execution_id": task.id,
                "runtime": {"id": version.runtime_id, "version": version.runtime_version},
                "package": {"id": version.package_id, "sha256": version.package_sha256, "size_bytes": version.package_size_bytes},
                "execution": {"mode": version.execution_mode, "timeout_seconds": version.timeout_seconds},
                "resources": version.resources,
                "required_capabilities": version.required_capabilities,
                "required_pools": version.required_pools,
                "exclusive_resources": version.exclusive_resources,
                "selection_reason": selection.reason,
            },
            offered_at=now,
            expires_at=offer_expires_at,
            correlation_id=execution.correlation_id,
        )
        attempt = attempt.mark_offered(offer.id, now)
        attempt_dto = self.attempts.add(_attempt_to_dto(attempt))
        task_dto = self.tasks.save(replace(task_dto, current_attempt_number=attempt_number))
        offer_dto = self.offers.add(_offer_to_dto(offer))

        command_payload = _execution_offer_payload(offer_dto, task_dto, version, command.parameters)
        command_record = self.commands.create(selection.agent_id, "execution.offer", command_payload, expires_at=offer_expires_at)

        self.outbox.append_event("execution.created", "execution", execution.id, {"execution_id": execution.id}, execution.correlation_id)
        self.outbox.append_event("task_execution.ready", "task_execution", task.id, {"task_execution_id": task.id}, execution.correlation_id)
        self.outbox.append_event("task_execution.queued", "task_execution", task.id, {"task_execution_id": task.id}, execution.correlation_id)
        self.outbox.append_event("execution_attempt.created", "execution_attempt", attempt.id, {"execution_attempt_id": attempt.id}, execution.correlation_id)
        self.outbox.append_event("execution_offer.created", "execution_offer", offer.id, {"execution_offer_id": offer.id, "command_id": command_record.id}, execution.correlation_id)
        _audit(self.audit, command.actor, "execution.created", "execution", execution.id, after={"automation_version_id": version.automation_version_id})
        if command.agent_id:
            _audit(self.audit, command.actor, "execution.manual_agent_selected", "agent", command.agent_id, after={"execution_id": execution.id})

        details = ExecutionDetailsDTO(
            execution=execution_dto,
            tasks=[task_dto],
            attempts=[attempt_dto],
            current_attempt=attempt_dto,
            current_offer=offer_dto,
            agent=self.agent_selection.get_agent_summary(selection.agent_id),
            automation_version=version,
        )
        if command.idempotency_key:
            self.idempotency.save_response("execution.create", command.idempotency_key, 201, details.to_payload(), execution.id)
        self.transaction.commit()
        return details

    def _reserve_idempotency(self, command: CreateAutomationExecutionCommand) -> None:
        if not command.idempotency_key:
            return
        request_hash = command.request_hash or ""
        status = self.idempotency.reserve(
            IdempotencyRecord(
                key=command.idempotency_key,
                scope="execution.create",
                request_hash=request_hash,
                expires_at=utcnow() + timedelta(hours=24),
            )
        )
        if status == IdempotencyReplayStatus.CONFLICT:
            self.transaction.rollback()
            raise IdempotencyConflict("Idempotency-Key was already used with a different payload.")
        if status == IdempotencyReplayStatus.REPLAY:
            record = self.idempotency.get("execution.create", command.idempotency_key)
            resource_id = record.resource_id if record else None
            if resource_id:
                self.transaction.rollback()
                raise _IdempotencyReplay(resource_id)
            self.transaction.rollback()
            raise IdempotencyConflict("Idempotency-Key replay is still pending.")


class GetExecution:
    def __init__(self, executions: ExecutionRepository) -> None:
        self.executions = executions

    def execute(self, execution_id: str) -> ExecutionDTO:
        execution = self.executions.get(execution_id)
        if execution is None:
            raise ExecutionNotFound("Execution not found.")
        return execution


class ListExecutions:
    def __init__(self, executions: ExecutionRepository) -> None:
        self.executions = executions

    def execute(self, limit: int = 100, offset: int = 0) -> list[ExecutionDTO]:
        return self.executions.list(limit=limit, offset=offset)


class GetExecutionDetails:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        automation_versions: AutomationVersionReader,
        agent_selection: AgentSelectionPort,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.offers = offers
        self.automation_versions = automation_versions
        self.agent_selection = agent_selection

    def execute(self, execution_id: str) -> ExecutionDetailsDTO:
        execution = self.executions.get(execution_id)
        if execution is None:
            raise ExecutionNotFound("Execution not found.")
        tasks = self.tasks.list_for_execution(execution_id)
        attempts = self.attempts.list_for_execution(execution_id)
        current_attempt = attempts[-1] if attempts else None
        current_offer = self.offers.current_for_execution(execution_id) if current_attempt else None
        version = self.automation_versions.get_published_snapshot(tasks[0].automation_version_id) if tasks else None
        agent = self.agent_selection.get_agent_summary(current_attempt.agent_id) if current_attempt else None
        return ExecutionDetailsDTO(
            execution=execution,
            tasks=tasks,
            attempts=attempts,
            current_attempt=current_attempt,
            current_offer=current_offer,
            agent=agent,
            automation_version=version,
        )


class SelectInitialAgent:
    def __init__(self, agent_selection: AgentSelectionPort) -> None:
        self.agent_selection = agent_selection

    def execute(self, request: AgentSelectionRequestDTO):
        return self.agent_selection.select(request)


class CreateTaskExecution:
    def __init__(self, tasks: TaskExecutionRepository) -> None:
        self.tasks = tasks

    def execute(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        return self.tasks.add(task)


class MarkTaskReady:
    def __init__(self, tasks: TaskExecutionRepository) -> None:
        self.tasks = tasks

    def execute(self, task_execution_id: str) -> TaskExecutionDTO:
        task = _require_task(self.tasks, task_execution_id)
        return self.tasks.save(_task_to_dto(_task_from_dto(task).mark_ready(utcnow())))


class QueueTaskExecution:
    def __init__(self, tasks: TaskExecutionRepository) -> None:
        self.tasks = tasks

    def execute(self, task_execution_id: str) -> TaskExecutionDTO:
        task = _require_task(self.tasks, task_execution_id)
        return self.tasks.save(_task_to_dto(_task_from_dto(task).mark_queued(utcnow())))


class CreateExecutionAttempt:
    def __init__(self, attempts: ExecutionAttemptRepository) -> None:
        self.attempts = attempts

    def execute(self, attempt: ExecutionAttemptDTO) -> ExecutionAttemptDTO:
        return self.attempts.add(attempt)


class GetExecutionAttempt:
    def __init__(self, attempts: ExecutionAttemptRepository) -> None:
        self.attempts = attempts

    def execute(self, execution_attempt_id: str) -> ExecutionAttemptDTO:
        attempt = self.attempts.get(execution_attempt_id)
        if attempt is None:
            raise ExecutionNotFound("ExecutionAttempt not found.")
        return attempt


class ListExecutionAttempts:
    def __init__(self, attempts: ExecutionAttemptRepository) -> None:
        self.attempts = attempts

    def execute(self, execution_id: str) -> list[ExecutionAttemptDTO]:
        return self.attempts.list_for_execution(execution_id)


class CreateExecutionOffer:
    def __init__(self, offers: ExecutionOfferRepository) -> None:
        self.offers = offers

    def execute(self, offer: ExecutionOfferDTO) -> ExecutionOfferDTO:
        return self.offers.add(offer)


class AcceptExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.offers = offers
        self.reservations = reservations
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, offer_id: str, attempt_id: str, agent_id: str, agent_instance_id: str) -> ExecutionOfferDTO:
        offer_dto = _require_offer(self.offers, offer_id)
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        if offer_dto.execution_attempt_id != attempt_id:
            self.transaction.rollback()
            raise ExecutionSecurityError("Offer and attempt do not match.")
        if offer_dto.status in {ExecutionOfferStatus.ACCEPTED.value, ExecutionOfferStatus.COMMITTED.value}:
            self.transaction.commit()
            return offer_dto
        now = utcnow()
        offer = _offer_from_dto(offer_dto).accept(agent_id=agent_id, agent_instance_id=agent_instance_id, now=now)
        attempt = _attempt_from_dto(attempt_dto).mark_accepted(now)
        saved_offer = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        for pool_type in saved_offer.requirements_snapshot.get("required_pools") or []:
            self.reservations.reserve(
                _reservation_to_dto(
                    ResourceReservation.create(
                        id=new_id("res"),
                        execution_offer_id=saved_offer.id,
                        execution_attempt_id=attempt.id,
                        agent_id=agent_id,
                        agent_instance_id=agent_instance_id,
                        pool_type=pool_type,
                        quantity=1,
                        expires_at=saved_offer.expires_at,
                        now=now,
                    )
                )
            )
        self.outbox.append_event("execution_offer.accepted", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id})
        self.transaction.commit()
        return saved_offer


class RejectExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.offers = offers
        self.reservations = reservations
        self.outbox = outbox
        self.transaction = transaction

    def execute(
        self,
        *,
        offer_id: str,
        attempt_id: str,
        agent_id: str,
        agent_instance_id: str,
        rejection_code: str,
        rejection_details: dict[str, Any] | None,
    ) -> ExecutionOfferDTO:
        offer_dto = _require_offer(self.offers, offer_id)
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        if offer_dto.execution_attempt_id != attempt_id:
            self.transaction.rollback()
            raise ExecutionSecurityError("Offer and attempt do not match.")
        if offer_dto.status == ExecutionOfferStatus.REJECTED.value:
            self.transaction.commit()
            return offer_dto
        now = utcnow()
        code = RejectionCode(rejection_code)
        offer = _offer_from_dto(offer_dto).reject(
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            code=code,
            details=rejection_details,
            now=now,
        )
        attempt = _attempt_from_dto(attempt_dto).mark_rejected(code.value, str(rejection_details or ""), now)
        saved_offer = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        self.reservations.release_for_offer(saved_offer.id, now)
        self.outbox.append_event("execution_offer.rejected", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id, "rejection_code": code.value})
        self.transaction.commit()
        return saved_offer


class ExpireExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.offers = offers
        self.reservations = reservations
        self.outbox = outbox
        self.transaction = transaction

    def execute_due(self, limit: int = 100) -> dict[str, int]:
        now = utcnow()
        count = 0
        for offer_dto in self.offers.due_for_expiration(now, limit=limit):
            self._expire_one(offer_dto, now)
            count += 1
        self.transaction.commit()
        return {"expired": count}

    def execute(self, offer_id: str) -> ExecutionOfferDTO:
        now = utcnow()
        offer = self._expire_one(_require_offer(self.offers, offer_id), now)
        self.transaction.commit()
        return offer

    def _expire_one(self, offer_dto: ExecutionOfferDTO, now: datetime) -> ExecutionOfferDTO:
        attempt_dto = _require_attempt(self.attempts, offer_dto.execution_attempt_id)
        if offer_dto.status == ExecutionOfferStatus.EXPIRED.value:
            return offer_dto
        offer = _offer_from_dto(offer_dto).expire(now)
        attempt = _attempt_from_dto(attempt_dto).mark_expired(now)
        saved_offer = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        self.reservations.release_for_offer(saved_offer.id, now)
        self.outbox.append_event("execution_offer.expired", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id})
        return saved_offer


class CommitExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        commands: AgentCommandPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.offers = offers
        self.commands = commands
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, offer_id: str, attempt_id: str, agent_id: str, agent_instance_id: str) -> dict[str, Any]:
        offer_dto = _require_offer(self.offers, offer_id)
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        if offer_dto.execution_attempt_id != attempt_id or offer_dto.agent_id != agent_id or offer_dto.agent_instance_id != agent_instance_id:
            self.transaction.rollback()
            raise ExecutionSecurityError("Offer, attempt, Agent and AgentInstance do not match.")
        if offer_dto.status == ExecutionOfferStatus.COMMITTED.value:
            self.transaction.commit()
            return {"offer": offer_dto, "command_id": None, "idempotent": True}
        now = utcnow()
        commit_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(commit_token.encode("utf-8")).hexdigest()
        lease_expires_at = now + timedelta(minutes=10)
        offer = _offer_from_dto(offer_dto).commit(token_hash=token_hash, token_expires_at=lease_expires_at, now=now)
        attempt = _attempt_from_dto(attempt_dto).mark_committed(now)
        saved_offer = self.offers.save(_offer_to_dto(offer), commit_token_hash=token_hash)
        self.attempts.save(_attempt_to_dto(attempt))
        command = self.commands.create(
            agent_id,
            "execution.commit",
            {
                "execution_offer_id": saved_offer.id,
                "execution_attempt_id": attempt.id,
                "lease_id": commit_token,
                "lease_expires_at": lease_expires_at.isoformat(),
            },
            expires_at=lease_expires_at,
        )
        self.outbox.append_event("execution_offer.committed", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id, "command_id": command.id})
        self.transaction.commit()
        return {"offer": saved_offer, "command_id": command.id, "idempotent": False}


class HandleExecutionStarted:
    def __init__(
        self,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.offers = offers
        self.reservations = reservations
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, attempt_id: str, offer_id: str | None, agent_id: str, agent_instance_id: str, started_at: Any = None) -> ExecutionDetailsDTO:
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        if attempt_dto.agent_id != agent_id or attempt_dto.agent_instance_id != agent_instance_id:
            self.transaction.rollback()
            raise ExecutionSecurityError("ExecutionAttempt belongs to another Agent or AgentInstance.")
        task_dto = _require_task(self.tasks, attempt_dto.task_execution_id)
        execution_dto = _require_execution(self.executions, task_dto.execution_id)
        if offer_id and attempt_dto.offer_id != offer_id:
            self.transaction.rollback()
            raise ExecutionSecurityError("Started offer does not match the attempt.")
        now = parse_datetime(started_at, utcnow())
        if attempt_dto.status != ExecutionAttemptStatus.RUNNING.value:
            attempt = _attempt_from_dto(attempt_dto).mark_running(now)
            attempt_dto = self.attempts.save(_attempt_to_dto(attempt))
        if task_dto.status != TaskExecutionStatus.RUNNING.value:
            task_dto = self.tasks.save(_task_to_dto(_task_from_dto(task_dto).mark_running(now)))
        if execution_dto.status != ExecutionStatus.RUNNING.value:
            execution_dto = self.executions.save(_execution_to_dto(_execution_from_dto(execution_dto).mark_running(now)))
        if attempt_dto.offer_id:
            self.reservations.convert_for_offer(attempt_dto.offer_id, now)
        self.outbox.append_event("execution.started", "execution", execution_dto.id, {"execution_id": execution_dto.id, "execution_attempt_id": attempt_dto.id})
        self.transaction.commit()
        return ExecutionDetailsDTO(
            execution=execution_dto,
            tasks=[task_dto],
            attempts=[attempt_dto],
            current_attempt=attempt_dto,
            current_offer=self.offers.current_for_attempt(attempt_dto.id),
            agent=None,
            automation_version=None,
        )


class CalculateExecutionStatus:
    def execute(self, task_statuses: list[str]) -> str:
        return calculate_execution_status([TaskExecutionStatus(status) for status in task_statuses]).value


class CalculateTaskExecutionStatus:
    def execute(self, attempt_running: bool, current_status: str) -> str:
        return calculate_task_execution_status(attempt_running, TaskExecutionStatus(current_status)).value


class _IdempotencyReplay(Exception):
    def __init__(self, resource_id: str) -> None:
        super().__init__(resource_id)
        self.resource_id = resource_id


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.utcnow()


def parse_datetime(value: Any, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return default
    return default


def _execution_offer_payload(offer: ExecutionOfferDTO, task: TaskExecutionDTO, version, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_offer_id": offer.id,
        "execution_attempt_id": offer.execution_attempt_id,
        "task_execution_id": task.id,
        "automation_version_id": str(version.automation_version_id),
        "runtime": {"id": version.runtime_id, "version": version.runtime_version},
        "package": {"id": version.package_id, "sha256": version.package_sha256, "size_bytes": version.package_size_bytes},
        "input": {"parameters": parameters},
        "required_capabilities": version.required_capabilities,
        "required_pools": version.required_pools,
        "resource_locks": version.exclusive_resources,
        "expires_at": offer.expires_at.isoformat(),
    }


def _audit(audit_repo, actor, action: str, resource_type: str, resource_id: str, after: dict[str, Any] | None = None) -> None:
    if audit_repo is None:
        return
    audit_repo.append(
        AuditEvent(
            id=str(uuid4()),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            after=after,
            metadata={"actor_email": actor.actor_email} if actor.actor_email else {},
            ip=actor.ip,
            user_agent=actor.user_agent,
            occurred_at=utcnow(),
        )
    )


def _require_execution(executions: ExecutionRepository, execution_id: str) -> ExecutionDTO:
    execution = executions.get(execution_id)
    if execution is None:
        raise ExecutionNotFound("Execution not found.")
    return execution


def _require_task(tasks: TaskExecutionRepository, task_execution_id: str) -> TaskExecutionDTO:
    task = tasks.get(task_execution_id)
    if task is None:
        raise ExecutionNotFound("TaskExecution not found.")
    return task


def _require_attempt(attempts: ExecutionAttemptRepository, attempt_id: str) -> ExecutionAttemptDTO:
    attempt = attempts.get(attempt_id)
    if attempt is None:
        raise ExecutionNotFound("ExecutionAttempt not found.")
    return attempt


def _require_offer(offers: ExecutionOfferRepository, offer_id: str) -> ExecutionOfferDTO:
    offer = offers.get(offer_id)
    if offer is None:
        raise ExecutionNotFound("ExecutionOffer not found.")
    return offer


def _execution_to_dto(execution: Execution) -> ExecutionDTO:
    return ExecutionDTO(
        id=execution.id,
        type=execution.type.value,
        origin=execution.origin.value,
        status=execution.status.value,
        requested_by=execution.requested_by,
        organization_id=execution.organization_id,
        input=execution.input,
        result=execution.result,
        correlation_id=execution.correlation_id,
        idempotency_key=execution.idempotency_key,
        created_at=execution.created_at,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        failure_summary=execution.failure_summary,
    )


def _execution_from_dto(dto: ExecutionDTO) -> Execution:
    return Execution(
        id=dto.id,
        type=ExecutionType(dto.type),
        origin=ExecutionOrigin(dto.origin),
        status=ExecutionStatus(dto.status),
        requested_by=dto.requested_by,
        organization_id=dto.organization_id,
        input=dto.input,
        result=dto.result,
        correlation_id=dto.correlation_id,
        idempotency_key=dto.idempotency_key,
        created_at=dto.created_at,
        started_at=dto.started_at,
        completed_at=dto.completed_at,
        failure_summary=dto.failure_summary,
    )


def _task_to_dto(task: TaskExecution) -> TaskExecutionDTO:
    return TaskExecutionDTO(
        id=task.id,
        execution_id=task.execution_id,
        automation_version_id=task.automation_version_id,
        status=task.status.value,
        priority=task.priority,
        parameters=task.parameters,
        input=task.input,
        result=task.result,
        retry_policy=task.retry_policy,
        timeout_policy=task.timeout_policy,
        created_at=task.created_at,
        ready_at=task.ready_at,
        queued_at=task.queued_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        current_attempt_number=task.current_attempt_number,
        failure_summary=task.failure_summary,
    )


def _task_from_dto(dto: TaskExecutionDTO) -> TaskExecution:
    return TaskExecution(
        id=dto.id,
        execution_id=dto.execution_id,
        automation_version_id=dto.automation_version_id,
        status=TaskExecutionStatus(dto.status),
        priority=dto.priority,
        parameters=dto.parameters,
        input=dto.input,
        result=dto.result,
        retry_policy=dto.retry_policy,
        timeout_policy=dto.timeout_policy,
        created_at=dto.created_at,
        ready_at=dto.ready_at,
        queued_at=dto.queued_at,
        started_at=dto.started_at,
        completed_at=dto.completed_at,
        current_attempt_number=dto.current_attempt_number,
        failure_summary=dto.failure_summary,
    )


def _attempt_to_dto(attempt: ExecutionAttempt) -> ExecutionAttemptDTO:
    return ExecutionAttemptDTO(
        id=attempt.id,
        task_execution_id=attempt.task_execution_id,
        attempt_number=attempt.attempt_number,
        agent_id=attempt.agent_id,
        agent_instance_id=attempt.agent_instance_id,
        status=attempt.status.value,
        runtime_version_id=attempt.runtime_version_id,
        package_id=attempt.package_id,
        offer_id=attempt.offer_id,
        created_at=attempt.created_at,
        offered_at=attempt.offered_at,
        accepted_at=attempt.accepted_at,
        committed_at=attempt.committed_at,
        preparing_at=attempt.preparing_at,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
    )


def _attempt_from_dto(dto: ExecutionAttemptDTO) -> ExecutionAttempt:
    return ExecutionAttempt(
        id=dto.id,
        task_execution_id=dto.task_execution_id,
        attempt_number=dto.attempt_number,
        agent_id=dto.agent_id,
        agent_instance_id=dto.agent_instance_id,
        status=ExecutionAttemptStatus(dto.status),
        runtime_version_id=dto.runtime_version_id,
        package_id=dto.package_id,
        offer_id=dto.offer_id,
        created_at=dto.created_at,
        offered_at=dto.offered_at,
        accepted_at=dto.accepted_at,
        committed_at=dto.committed_at,
        preparing_at=dto.preparing_at,
        started_at=dto.started_at,
        completed_at=dto.completed_at,
        error_code=dto.error_code,
        error_message=dto.error_message,
    )


def _offer_to_dto(offer: ExecutionOffer) -> ExecutionOfferDTO:
    return ExecutionOfferDTO(
        id=offer.id,
        execution_attempt_id=offer.execution_attempt_id,
        agent_id=offer.agent_id,
        agent_instance_id=offer.agent_instance_id,
        status=offer.status.value,
        requirements_snapshot=offer.requirements_snapshot,
        offered_at=offer.offered_at,
        expires_at=offer.expires_at,
        responded_at=offer.responded_at,
        accepted_at=offer.accepted_at,
        committed_at=offer.committed_at,
        rejection_code=offer.rejection_code.value if offer.rejection_code else None,
        rejection_details=offer.rejection_details,
        correlation_id=offer.correlation_id,
        commit_token_expires_at=offer.commit_token_expires_at,
    )


def _offer_from_dto(dto: ExecutionOfferDTO) -> ExecutionOffer:
    return ExecutionOffer(
        id=dto.id,
        execution_attempt_id=dto.execution_attempt_id,
        agent_id=dto.agent_id,
        agent_instance_id=dto.agent_instance_id,
        status=ExecutionOfferStatus(dto.status),
        requirements_snapshot=dto.requirements_snapshot,
        offered_at=dto.offered_at,
        expires_at=dto.expires_at,
        responded_at=dto.responded_at,
        accepted_at=dto.accepted_at,
        committed_at=dto.committed_at,
        rejection_code=RejectionCode(dto.rejection_code) if dto.rejection_code else None,
        rejection_details=dto.rejection_details,
        correlation_id=dto.correlation_id,
        commit_token_expires_at=dto.commit_token_expires_at,
    )


def _reservation_to_dto(reservation: ResourceReservation) -> ResourceReservationDTO:
    return ResourceReservationDTO(
        id=reservation.id,
        execution_offer_id=reservation.execution_offer_id,
        execution_attempt_id=reservation.execution_attempt_id,
        agent_id=reservation.agent_id,
        agent_instance_id=reservation.agent_instance_id,
        pool_type=reservation.pool_type,
        quantity=reservation.quantity,
        status=reservation.status.value,
        expires_at=reservation.expires_at,
        created_at=reservation.created_at,
        released_at=reservation.released_at,
        converted_at=reservation.converted_at,
    )
