from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from modules.dispatch.application.dto import ExecutionLeaseDTO, LeaseRenewalCommand
from modules.dispatch.application.ports import (
    AgentCommandPort,
    ExecutionLeaseRepository,
    ExecutionOfferRepository,
    OfferReservationPort,
    OutboxPort,
    ResourceLockRepository,
    TransactionManager,
)
from modules.dispatch.domain.lease import ExecutionLease
from modules.dispatch.domain.offer import ExecutionOffer, RejectionCode
from modules.dispatch.domain.states import ExecutionLeaseStatus, ExecutionOfferStatus
from modules.orchestration.application.dto import ExecutionAttemptDTO, ExecutionOfferDTO
from modules.orchestration.application.ports import ExecutionAttemptRepository, TaskExecutionRepository
from modules.orchestration.domain.execution_attempt import ExecutionAttempt


class AcceptExecutionOffer:
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

    def execute(self, *, offer_id: str, attempt_id: str, agent_id: str, agent_instance_id: str) -> ExecutionOfferDTO:
        offer_dto = _require_offer(self.offers, offer_id)
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        _ensure_offer_matches(offer_dto, attempt_dto, agent_id, agent_instance_id)
        if offer_dto.status in {ExecutionOfferStatus.ACCEPTED.value, ExecutionOfferStatus.COMMITTED.value}:
            self.transaction.commit()
            return offer_dto
        now = utcnow()
        offer = _offer_from_dto(offer_dto).accept(agent_id=agent_id, agent_instance_id=agent_instance_id, now=now)
        attempt = _attempt_from_dto(attempt_dto).mark_accepted(now)
        saved_offer = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        self.commands.acknowledge_by_payload(agent_id, "execution.offer", "execution_offer_id", offer_id, "accepted", now)
        self.outbox.append_event("execution_offer.accepted", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id})
        self.transaction.commit()
        return saved_offer


class RejectExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        tasks: TaskExecutionRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        commands: AgentCommandPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.tasks = tasks
        self.offers = offers
        self.reservations = reservations
        self.locks = locks
        self.commands = commands
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
        _ensure_offer_matches(offer_dto, attempt_dto, agent_id, agent_instance_id)
        if offer_dto.status == ExecutionOfferStatus.REJECTED.value:
            self.transaction.commit()
            return offer_dto
        now = utcnow()
        code = RejectionCode(rejection_code)
        offer = _offer_from_dto(offer_dto).reject(agent_id=agent_id, agent_instance_id=agent_instance_id, code=code, details=rejection_details, now=now)
        attempt = _attempt_from_dto(attempt_dto).mark_rejected(code.value, str(rejection_details or ""), now)
        saved_offer = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        task = self.tasks.get(attempt.task_execution_id)
        if task is not None:
            self.tasks.save(replace(task, status="ready", available_at=now, last_scheduling_failure={"code": "AGENT_REJECTED", "agent_id": agent_id, "rejection_code": code.value}))
        self.reservations.release_for_offer(saved_offer.id, now)
        self.locks.release_for_attempt(attempt.id, now, "offer_rejected")
        self.commands.acknowledge_by_payload(agent_id, "execution.offer", "execution_offer_id", offer_id, "rejected", now)
        self.outbox.append_event("execution_offer.rejected", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id, "rejection_code": code.value})
        self.transaction.commit()
        return saved_offer


class CommitExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        leases: ExecutionLeaseRepository,
        commands: AgentCommandPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.offers = offers
        self.leases = leases
        self.commands = commands
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, offer_id: str, attempt_id: str, agent_id: str, agent_instance_id: str) -> dict[str, Any]:
        offer_dto = _require_offer(self.offers, offer_id)
        attempt_dto = _require_attempt(self.attempts, attempt_id)
        _ensure_offer_matches(offer_dto, attempt_dto, agent_id, agent_instance_id)
        existing_lease = self.leases.active_for_attempt(attempt_id)
        if offer_dto.status == ExecutionOfferStatus.COMMITTED.value and existing_lease is not None:
            self.transaction.commit()
            return {"offer": offer_dto, "lease": existing_lease, "command_id": None, "idempotent": True}
        now = utcnow()
        policy = offer_dto.requirements_snapshot.get("timeout_policy") if isinstance(offer_dto.requirements_snapshot.get("timeout_policy"), dict) else {}
        lease_duration = _positive_int(policy.get("lease_duration_seconds"), 600)
        lease_grace = _positive_int(policy.get("lease_grace_seconds"), 60)
        lease_expires_at = now + timedelta(seconds=lease_duration)
        lease = ExecutionLease.issue(
            id=new_id("lea"),
            execution_attempt_id=attempt_id,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            issued_at=now,
            expires_at=lease_expires_at,
            grace_until=lease_expires_at + timedelta(seconds=lease_grace),
        )
        offer = _offer_from_dto(offer_dto).commit(
            token_hash=hashlib.sha256(lease.id.encode("utf-8")).hexdigest(),
            token_expires_at=lease_expires_at,
            now=now,
        )
        attempt = _attempt_from_dto(attempt_dto).mark_committed(now)
        saved_offer = self.offers.save(_offer_to_dto(offer), commit_token_hash=hashlib.sha256(lease.id.encode("utf-8")).hexdigest())
        self.attempts.save(_attempt_to_dto(attempt))
        saved_lease = self.leases.add(_lease_to_dto(lease))
        requirements = offer_dto.requirements_snapshot if isinstance(offer_dto.requirements_snapshot, dict) else {}
        command = self.commands.create(
            agent_id,
            "execution.commit",
            {
                "execution_offer_id": saved_offer.id,
                "execution_id": requirements.get("execution_id"),
                "execution_attempt_id": attempt.id,
                "task_execution_id": attempt.task_execution_id,
                "agent_id": agent_id,
                "agent_instance_id": agent_instance_id,
                "lease_id": saved_lease.id,
                "lease_expires_at": saved_lease.expires_at.isoformat(),
            },
            expires_at=lease_expires_at,
        )
        self.outbox.append_event("execution_offer.committed", "execution_offer", saved_offer.id, {"execution_offer_id": saved_offer.id, "lease_id": saved_lease.id, "command_id": command.id})
        self.transaction.commit()
        return {"offer": saved_offer, "lease": saved_lease, "command_id": command.id, "idempotent": False}


class ExpireExecutionOffer:
    def __init__(
        self,
        attempts: ExecutionAttemptRepository,
        tasks: TaskExecutionRepository,
        offers: ExecutionOfferRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.attempts = attempts
        self.tasks = tasks
        self.offers = offers
        self.reservations = reservations
        self.locks = locks
        self.outbox = outbox
        self.transaction = transaction

    def execute_due(self, *, limit: int = 100) -> dict[str, int]:
        now = utcnow()
        expired = 0
        for offer in self.offers.due_for_expiration(now, limit=limit):
            self._expire_one(offer, now)
            expired += 1
        self.transaction.commit()
        return {"expired": expired}

    def _expire_one(self, offer_dto: ExecutionOfferDTO, now: datetime) -> ExecutionOfferDTO:
        if offer_dto.status == ExecutionOfferStatus.EXPIRED.value:
            return offer_dto
        attempt_dto = _require_attempt(self.attempts, offer_dto.execution_attempt_id)
        offer = _offer_from_dto(offer_dto).expire(now)
        attempt = _attempt_from_dto(attempt_dto).mark_expired(now)
        saved = self.offers.save(_offer_to_dto(offer))
        self.attempts.save(_attempt_to_dto(attempt))
        task = self.tasks.get(attempt.task_execution_id)
        if task is not None:
            self.tasks.save(replace(task, status="ready", available_at=now, last_scheduling_failure={"code": "OFFER_EXPIRED", "offer_id": saved.id}))
        self.reservations.release_for_offer(saved.id, now)
        self.locks.release_for_attempt(attempt.id, now, "offer_expired")
        self.outbox.append_event("execution_offer.expired", "execution_offer", saved.id, {"execution_offer_id": saved.id})
        return saved


class RenewExecutionLease:
    def __init__(self, attempts: ExecutionAttemptRepository, leases: ExecutionLeaseRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.attempts = attempts
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, command: LeaseRenewalCommand) -> ExecutionLeaseDTO:
        attempt = _require_attempt(self.attempts, command.execution_attempt_id)
        if attempt.agent_id != command.agent_id or attempt.agent_instance_id != command.agent_instance_id:
            self.transaction.rollback()
            raise ValueError("ExecutionAttempt belongs to another Agent or AgentInstance.")
        lease = self.leases.get(command.lease_id)
        if lease is None or lease.execution_attempt_id != command.execution_attempt_id:
            self.transaction.rollback()
            raise ValueError("ExecutionLease not found for attempt.")
        if lease.agent_id != command.agent_id or lease.agent_instance_id != command.agent_instance_id:
            self.transaction.rollback()
            raise ValueError("ExecutionLease belongs to another Agent or AgentInstance.")
        now = utcnow()
        if lease.status != "active":
            self.transaction.commit()
            return lease
        duration = max(int((_naive(lease.expires_at) - _naive(lease.issued_at)).total_seconds()), 60)
        grace = max(int((_naive(lease.grace_until) - _naive(lease.expires_at)).total_seconds()), 30)
        renewed = ExecutionLease(
            id=lease.id,
            execution_attempt_id=lease.execution_attempt_id,
            agent_id=lease.agent_id,
            agent_instance_id=lease.agent_instance_id,
            status=ExecutionLeaseStatus.ACTIVE,
            issued_at=lease.issued_at,
            expires_at=lease.expires_at,
            last_renewed_at=lease.last_renewed_at,
            renewal_sequence=lease.renewal_sequence,
            grace_until=lease.grace_until,
            revoked_at=lease.revoked_at,
            revocation_reason=lease.revocation_reason,
        ).renew(
            renewal_sequence=command.renewal_sequence,
            now=now,
            expires_at=now + timedelta(seconds=duration),
            grace_until=now + timedelta(seconds=duration + grace),
        )
        saved = self.leases.save(_lease_to_dto(renewed))
        self.outbox.append_event("execution_lease.renewed", "execution_attempt", attempt.id, {"execution_attempt_id": attempt.id, "lease_id": saved.id, "renewal_sequence": saved.renewal_sequence})
        self.transaction.commit()
        return saved


class ActivateAttemptDispatchResources:
    def __init__(self, reservations: OfferReservationPort, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.reservations = reservations
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, execution_attempt_id: str, offer_id: str | None = None) -> dict[str, Any]:
        now = utcnow()
        if offer_id:
            self.reservations.convert_for_offer(offer_id, now)
        self.outbox.append_event("dispatch.resources.activated", "execution_attempt", execution_attempt_id, {"execution_attempt_id": execution_attempt_id, "offer_id": offer_id})
        return {"execution_attempt_id": execution_attempt_id, "offer_id": offer_id, "status": "active"}


class ReleaseAttemptDispatchResources:
    def __init__(self, reservations: OfferReservationPort, locks: ResourceLockRepository, leases: ExecutionLeaseRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.reservations = reservations
        self.locks = locks
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, execution_attempt_id: str, reason: str) -> dict[str, Any]:
        now = utcnow()
        self.reservations.release_for_attempt(execution_attempt_id, now, reason)
        self.locks.release_for_attempt(execution_attempt_id, now, reason)
        lease = self.leases.active_for_attempt(execution_attempt_id)
        if lease is not None:
            self.leases.save(replace(lease, status="completed", revoked_at=now, revocation_reason=reason))
        self.outbox.append_event("dispatch.resources.released", "execution_attempt", execution_attempt_id, {"execution_attempt_id": execution_attempt_id, "reason": reason})
        return {"execution_attempt_id": execution_attempt_id, "released": True}


def _ensure_offer_matches(offer: ExecutionOfferDTO, attempt: ExecutionAttemptDTO, agent_id: str, agent_instance_id: str) -> None:
    if offer.execution_attempt_id != attempt.id or offer.agent_id != agent_id or offer.agent_instance_id != agent_instance_id:
        raise ValueError("Offer, attempt, Agent and AgentInstance do not match.")


def _require_attempt(attempts: ExecutionAttemptRepository, attempt_id: str) -> ExecutionAttemptDTO:
    attempt = attempts.get(attempt_id)
    if attempt is None:
        raise ValueError("ExecutionAttempt not found.")
    return attempt


def _require_offer(offers: ExecutionOfferRepository, offer_id: str) -> ExecutionOfferDTO:
    offer = offers.get(offer_id)
    if offer is None:
        raise ValueError("ExecutionOffer not found.")
    return offer


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


def _attempt_from_dto(dto: ExecutionAttemptDTO) -> ExecutionAttempt:
    from modules.orchestration.domain.states import ExecutionAttemptStatus

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
        exit_code=dto.exit_code,
        output=dto.output,
        result=dto.result,
        resource_usage=dto.resource_usage,
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
        exit_code=attempt.exit_code,
        output=attempt.output,
        result=attempt.result,
        resource_usage=attempt.resource_usage,
    )


def _lease_to_dto(lease: ExecutionLease) -> ExecutionLeaseDTO:
    return ExecutionLeaseDTO(
        id=lease.id,
        execution_attempt_id=lease.execution_attempt_id,
        agent_id=lease.agent_id,
        agent_instance_id=lease.agent_instance_id,
        status=lease.status.value if hasattr(lease.status, "value") else str(lease.status),
        issued_at=lease.issued_at,
        expires_at=lease.expires_at,
        last_renewed_at=lease.last_renewed_at,
        renewal_sequence=lease.renewal_sequence,
        grace_until=lease.grace_until,
        revoked_at=lease.revoked_at,
        revocation_reason=lease.revocation_reason,
    )


def _positive_int(value: Any, default: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return default
    return candidate if candidate > 0 else default


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def utcnow() -> datetime:
    return datetime.utcnow()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
