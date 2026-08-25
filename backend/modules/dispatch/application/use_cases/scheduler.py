from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from modules.dispatch.application.dto import DispatchDecisionDTO, ScheduleReadyTasksResultDTO, ScheduleTaskResultDTO, to_payload
from modules.dispatch.application.ports import (
    AgentCommandPort,
    DispatchCandidateReader,
    DispatchDecisionRepository,
    ExecutionOfferRepository,
    OfferReservationPort,
    ReadyTaskRepository,
    ResourceLockRepository,
    TransactionManager,
)
from modules.dispatch.domain.candidate import DispatchCandidate
from modules.dispatch.domain.offer import ExecutionOffer
from modules.dispatch.domain.reservation import ResourceReservation
from modules.dispatch.domain.resource_lock import ResourceLock, normalize_resource_key
from modules.dispatch.domain.scoring import CandidateScoreInput, CandidateScoringWeights, calculate_candidate_score
from modules.dispatch.domain.states import DispatchDecisionStatus
from modules.orchestration.application.dto import AutomationVersionSnapshotDTO, ExecutionAttemptDTO, ResourceReservationDTO, TaskExecutionDTO
from modules.orchestration.application.ports import AutomationVersionReader, ExecutionAttemptRepository, OutboxPort
from modules.orchestration.domain.execution_attempt import ExecutionAttempt


class ScheduleReadyTasks:
    def __init__(
        self,
        ready_tasks: ReadyTaskRepository,
        scheduler: "ScheduleTaskExecution",
        transaction: TransactionManager,
    ) -> None:
        self.ready_tasks = ready_tasks
        self.scheduler = scheduler
        self.transaction = transaction

    def execute(self, *, limit: int = 20, scheduler_run_id: str | None = None) -> ScheduleReadyTasksResultDTO:
        run_id = scheduler_run_id or new_id("schrun")
        now = utcnow()
        tasks = self.ready_tasks.claim_ready(now, limit)
        results: list[ScheduleTaskResultDTO] = []
        scheduled = 0
        skipped = 0
        for task in tasks:
            result = self.scheduler.execute(task.id, scheduler_run_id=run_id, claimed_task=task)
            results.append(result)
            if result.scheduled:
                scheduled += 1
            else:
                skipped += 1
        return ScheduleReadyTasksResultDTO(scheduler_run_id=run_id, scanned=len(tasks), scheduled=scheduled, skipped=skipped, results=results)


class ScheduleTaskExecution:
    def __init__(
        self,
        ready_tasks: ReadyTaskRepository,
        attempts: ExecutionAttemptRepository,
        offers: ExecutionOfferRepository,
        automation_versions: AutomationVersionReader,
        candidates: DispatchCandidateReader,
        decisions: DispatchDecisionRepository,
        reservations: OfferReservationPort,
        locks: ResourceLockRepository,
        commands: AgentCommandPort,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.ready_tasks = ready_tasks
        self.attempts = attempts
        self.offers = offers
        self.automation_versions = automation_versions
        self.candidates = candidates
        self.decisions = decisions
        self.reservations = reservations
        self.locks = locks
        self.commands = commands
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, task_execution_id: str, *, scheduler_run_id: str | None = None, claimed_task: TaskExecutionDTO | None = None) -> ScheduleTaskResultDTO:
        run_id = scheduler_run_id or new_id("schrun")
        now = utcnow()
        task = claimed_task or self.ready_tasks.get(task_execution_id)
        if task is None:
            raise ValueError("TaskExecution not found.")
        requirements = _task_requirements(task, self.automation_versions)
        excluded_agent_ids = _rejected_agent_ids(self.attempts, task)
        evaluated = FindEligibleAgents(self.candidates, self.reservations, self.locks).execute(requirements, excluded_agent_ids=excluded_agent_ids, now=now)
        ranked = RankDispatchCandidates().execute(evaluated, requirements)
        selected = SelectBestAgent().execute(ranked)

        if selected is None:
            next_at = now + _scheduling_backoff(task.scheduling_attempts)
            failure = {
                "code": "NO_ELIGIBLE_AGENT",
                "message": "No eligible Agent was available for this TaskExecution.",
                "evaluated_candidates": len(ranked),
            }
            saved_task = self.ready_tasks.save(
                replace(
                    task,
                    available_at=next_at,
                    scheduling_attempts=task.scheduling_attempts + 1,
                    last_scheduling_attempt_at=now,
                    next_scheduling_attempt_at=next_at,
                    last_scheduling_failure=failure,
                )
            )
            decision = self.decisions.add(
                DispatchDecisionDTO(
                    id=new_id("dspdec"),
                    scheduler_run_id=run_id,
                    task_execution_id=task.id,
                    status=DispatchDecisionStatus.NO_CANDIDATE.value,
                    candidates=[candidate.to_payload() for candidate in ranked],
                    weights=CandidateScoringWeights.from_config(_scheduler_config(requirements).get("weights")).to_payload(),
                    decision_reason=failure["code"],
                    created_at=now,
                )
            )
            self.outbox.append_event("dispatch.no_candidate", "task_execution", task.id, {"task_execution_id": task.id, "decision_id": decision.id, "next_scheduling_attempt_at": next_at.isoformat()})
            self.transaction.commit()
            return ScheduleTaskResultDTO(task_execution_id=saved_task.id, scheduled=False, decision_id=decision.id, next_scheduling_attempt_at=next_at, reason=failure["code"])

        if not selected.agent_instance_id:
            raise ValueError("Selected Agent does not have an active AgentInstance.")
        attempt_number = self.attempts.next_attempt_number(task.id)
        attempt = ExecutionAttempt.create(
            id=new_id("att"),
            task_execution_id=task.id,
            attempt_number=attempt_number,
            agent_id=selected.agent_id,
            agent_instance_id=selected.agent_instance_id,
            runtime_version_id=str(requirements.get("runtime_version_id") or "") or None,
            package_id=str(requirements.get("package_id") or "") or None,
            now=now,
        )
        offer_timeout = _timeout_policy(requirements).get("offer_timeout_seconds", 60)
        offer_expires_at = now + timedelta(seconds=int(offer_timeout))
        offer = ExecutionOffer.create(
            id=new_id("off"),
            execution_attempt_id=attempt.id,
            agent_id=selected.agent_id,
            agent_instance_id=selected.agent_instance_id,
            requirements_snapshot={**requirements, "dispatch": {"selected_agent_id": selected.agent_id, "score": selected.score, "score_components": selected.score_components}},
            offered_at=now,
            expires_at=offer_expires_at,
            correlation_id=str(requirements.get("execution_id") or "") or None,
        )
        attempt = attempt.mark_offered(offer.id, now)
        attempt_dto = self.attempts.add(_attempt_to_dto(attempt))
        offer_dto = self.offers.add(_offer_to_dto(offer))
        self._reserve_pools(task, offer_dto.id, attempt_dto, selected, requirements, offer_expires_at, now)
        self._acquire_locks(attempt_dto, selected.agent_id, requirements, offer_expires_at, now)
        saved_task = self.ready_tasks.save(
            replace(
                task,
                status="queued",
                queued_at=task.queued_at or now,
                current_attempt_number=attempt_number,
                scheduling_attempts=task.scheduling_attempts + 1,
                last_scheduling_attempt_at=now,
                next_scheduling_attempt_at=None,
                last_scheduling_failure=None,
                requirements_snapshot=requirements,
            )
        )
        command = self.commands.create(selected.agent_id, "execution.offer", _execution_offer_payload(offer_dto, saved_task, requirements), expires_at=offer_expires_at)
        decision = self.decisions.add(
            DispatchDecisionDTO(
                id=new_id("dspdec"),
                scheduler_run_id=run_id,
                task_execution_id=task.id,
                execution_attempt_id=attempt_dto.id,
                execution_offer_id=offer_dto.id,
                selected_agent_id=selected.agent_id,
                selected_agent_instance_id=selected.agent_instance_id,
                status=DispatchDecisionStatus.SELECTED.value,
                candidates=[candidate.to_payload() for candidate in ranked],
                weights=CandidateScoringWeights.from_config(_scheduler_config(requirements).get("weights")).to_payload(),
                decision_reason="highest_score",
                metadata={"command_id": command.id},
                created_at=now,
            )
        )
        self.outbox.append_event("execution_attempt.created", "execution_attempt", attempt.id, {"execution_attempt_id": attempt.id, "task_execution_id": task.id})
        self.outbox.append_event("execution_offer.created", "execution_offer", offer.id, {"execution_offer_id": offer.id, "command_id": command.id, "dispatch_decision_id": decision.id})
        self.transaction.commit()
        return ScheduleTaskResultDTO(
            task_execution_id=task.id,
            scheduled=True,
            decision_id=decision.id,
            execution_attempt_id=attempt.id,
            execution_offer_id=offer.id,
            agent_id=selected.agent_id,
            agent_instance_id=selected.agent_instance_id,
            command_id=command.id,
        )

    def _reserve_pools(self, task: TaskExecutionDTO, offer_id: str, attempt: ExecutionAttemptDTO, selected: DispatchCandidate, requirements: dict[str, Any], expires_at: datetime, now: datetime) -> None:
        for pool_type in _required_pools(requirements):
            reservation = ResourceReservation.create(
                id=new_id("res"),
                task_execution_id=task.id,
                execution_offer_id=offer_id,
                execution_attempt_id=attempt.id,
                agent_id=selected.agent_id,
                agent_instance_id=selected.agent_instance_id or "",
                pool_type=pool_type,
                units=1,
                expires_at=expires_at,
                now=now,
            )
            self.reservations.reserve(_reservation_to_dto(reservation))

    def _acquire_locks(self, attempt: ExecutionAttemptDTO, agent_id: str, requirements: dict[str, Any], expires_at: datetime, now: datetime) -> None:
        for resource in _exclusive_resources(requirements):
            key = str(resource.get("key") if isinstance(resource, dict) else resource)
            scope = str(resource.get("scope") if isinstance(resource, dict) else "global") or "global"
            normalized = normalize_resource_key(key)
            if self.locks.active_conflict(normalized, scope) is not None:
                raise ValueError(f"Resource lock conflict for {scope}:{key}.")
            lock = ResourceLock.acquire(
                id=new_id("lock"),
                resource_key=key,
                scope=scope,
                agent_id=agent_id,
                execution_attempt_id=attempt.id,
                acquired_at=now,
                expires_at=expires_at,
            )
            self.locks.add(_lock_to_dto(lock))


class FindEligibleAgents:
    def __init__(self, candidates: DispatchCandidateReader, reservations: OfferReservationPort, locks: ResourceLockRepository) -> None:
        self.candidates = candidates
        self.reservations = reservations
        self.locks = locks

    def execute(self, requirements: dict[str, Any], *, excluded_agent_ids: set[str] | None = None, now: datetime | None = None) -> list[DispatchCandidate]:
        now = now or utcnow()
        excluded = excluded_agent_ids or set()
        preferred_agent_id = requirements.get("preferred_agent_id") if isinstance(requirements.get("preferred_agent_id"), str) else None
        snapshots = self.candidates.list_candidates(preferred_agent_id=preferred_agent_id)
        result: list[DispatchCandidate] = []
        for snapshot in snapshots:
            candidate = DispatchCandidate.pending(
                agent_id=snapshot.agent_id,
                agent_instance_id=snapshot.agent_instance_id,
                worker_id=snapshot.worker_id,
                evaluated_at=now,
                snapshot_revision=snapshot.snapshot_revision,
            )
            candidate = self._apply_filters(candidate, snapshot, requirements, excluded, now)
            result.append(candidate)
        return result

    def _apply_filters(self, candidate: DispatchCandidate, snapshot, requirements: dict[str, Any], excluded_agent_ids: set[str], now: datetime) -> DispatchCandidate:
        if candidate.agent_id in excluded_agent_ids:
            candidate = candidate.reject("AGENT_ALREADY_REJECTED", "Agent already rejected this TaskExecution.")
        if not snapshot.enabled:
            candidate = candidate.reject("AGENT_DISABLED", "Agent is disabled.")
        if snapshot.administrative_status in {"disabled", "maintenance", "updating", "draining"}:
            candidate = candidate.reject(f"AGENT_{snapshot.administrative_status.upper()}", f"Agent administrative_status={snapshot.administrative_status}.")
        if snapshot.connectivity_status != "online":
            candidate = candidate.reject("AGENT_OFFLINE", "Agent is not online.", connectivity_status=snapshot.connectivity_status)
        if not snapshot.agent_instance_id:
            candidate = candidate.reject("AGENT_INSTANCE_MISSING", "Agent does not have an active instance.")
        if snapshot.protocol_version != "1.0":
            candidate = candidate.reject("PROTOCOL_INCOMPATIBLE", "Agent protocol is not compatible.", protocol_version=snapshot.protocol_version)
        if snapshot.snapshot_expires_at is None or _naive(snapshot.snapshot_expires_at) <= _naive(now):
            candidate = candidate.reject("RESOURCE_SNAPSHOT_EXPIRED", "Agent resource snapshot is missing or expired.")

        profile = snapshot.machine_profile or {}
        required_os = requirements.get("operating_system") or (requirements.get("runtime") or {}).get("operating_system")
        required_arch = requirements.get("architecture") or (requirements.get("runtime") or {}).get("architecture")
        if required_os and profile.get("operating_system") and str(required_os).lower() not in str(profile.get("operating_system")).lower():
            candidate = candidate.reject("OPERATING_SYSTEM_INCOMPATIBLE", "Agent operating system is incompatible.", required=required_os, observed=profile.get("operating_system"))
        if required_arch and profile.get("architecture") and str(required_arch).lower() != str(profile.get("architecture")).lower():
            candidate = candidate.reject("ARCHITECTURE_INCOMPATIBLE", "Agent architecture is incompatible.", required=required_arch, observed=profile.get("architecture"))

        capabilities = {item.get("key"): item for item in snapshot.capabilities if item.get("status") in {"available", "active", "ok"}}
        runtime_id = (requirements.get("runtime") or {}).get("id")
        declared_runtime_caps = [key for key in capabilities if str(key).startswith(("runtime.", "runtime:"))]
        if declared_runtime_caps and runtime_id and f"runtime.{runtime_id}" not in capabilities and f"runtime:{runtime_id}" not in capabilities:
            candidate = candidate.reject("RUNTIME_UNAVAILABLE", "Required runtime is not available.", runtime_id=runtime_id)
        for requirement in _required_capabilities(requirements):
            key = requirement.get("key") if isinstance(requirement, dict) else str(requirement)
            if key and key not in capabilities:
                candidate = candidate.reject("CAPABILITY_UNAVAILABLE", "Required capability is unavailable.", capability=key)

        if requirements.get("execution_mode") == "interactive":
            session = snapshot.interactive_session or {}
            if session.get("available") is not True:
                candidate = candidate.reject("INTERACTIVE_SESSION_UNAVAILABLE", "Interactive session is unavailable.")
            if session.get("locked") is True:
                candidate = candidate.reject("INTERACTIVE_SESSION_LOCKED", "Interactive session is locked.")
            if session.get("expires_at") and _naive(session["expires_at"]) <= _naive(now):
                candidate = candidate.reject("INTERACTIVE_SESSION_EXPIRED", "Interactive session snapshot expired.")

        resources = _resource_requirements(requirements)
        if snapshot.memory_available_mb is not None and snapshot.memory_available_mb < resources.get("memory_mb", 0):
            candidate = candidate.reject("INSUFFICIENT_MEMORY", "Agent memory is insufficient.", required_mb=resources.get("memory_mb"), available_mb=snapshot.memory_available_mb)
        if snapshot.disk_free_mb is not None and snapshot.disk_free_mb < resources.get("disk_mb", 0):
            candidate = candidate.reject("INSUFFICIENT_DISK", "Agent disk is insufficient.", required_mb=resources.get("disk_mb"), available_mb=snapshot.disk_free_mb)
        if snapshot.cpu_usage_percentage is not None and snapshot.cpu_usage_percentage >= 95:
            candidate = candidate.reject("INSUFFICIENT_CPU_CAPACITY", "Agent CPU usage is too high.", cpu_usage_percentage=snapshot.cpu_usage_percentage)

        available_units: list[int] = []
        for pool_type in _required_pools(requirements):
            pool = snapshot.pools.get(pool_type)
            persistent_reserved = self.reservations.active_units(snapshot.agent_id, pool_type)
            available = (pool or {}).get("available") if isinstance(pool, dict) else None
            if available is not None:
                available_units.append(max(int(available) - persistent_reserved, 0))
            if available is None or int(available) - persistent_reserved <= 0:
                candidate = candidate.reject("POOL_UNAVAILABLE", "Required pool is unavailable.", pool_type=pool_type)

        for resource in _exclusive_resources(requirements):
            key = str(resource.get("key") if isinstance(resource, dict) else resource)
            scope = str(resource.get("scope") if isinstance(resource, dict) else "global") or "global"
            conflict = self.locks.active_conflict(normalize_resource_key(key), scope)
            if conflict is not None:
                candidate = candidate.reject("RESOURCE_LOCKED", "Exclusive resource is already locked.", resource_key=key, scope=scope)
        package_id = (requirements.get("package") or {}).get("id") or requirements.get("package_id")
        return candidate.with_facts(
            {
                "available_pool_units": min(available_units) if available_units else 0,
                "cpu_usage_percentage": snapshot.cpu_usage_percentage,
                "memory_available_mb": snapshot.memory_available_mb,
                "package_cached": bool(package_id and (f"package.{package_id}" in capabilities or f"package:{package_id}" in capabilities)),
                "runtime_cached": bool(runtime_id and (f"runtime.{runtime_id}" in capabilities or f"runtime:{runtime_id}" in capabilities)),
                "active_attempts": snapshot.active_attempts,
            }
        )


class RankDispatchCandidates:
    def execute(self, candidates: list[DispatchCandidate], requirements: dict[str, Any]) -> list[DispatchCandidate]:
        weights = CandidateScoringWeights.from_config(_scheduler_config(requirements).get("weights"))
        ranked: list[DispatchCandidate] = []
        for candidate in candidates:
            if not candidate.eligible:
                ranked.append(candidate)
                continue
            facts = candidate.facts
            components_input = CandidateScoreInput(
                available_pool_units=int(facts.get("available_pool_units") or 0),
                required_pool_units=1,
                cpu_usage_percentage=facts.get("cpu_usage_percentage"),
                memory_available_mb=facts.get("memory_available_mb"),
                memory_required_mb=_resource_requirements(requirements).get("memory_mb", 1),
                package_cached=bool(facts.get("package_cached")),
                runtime_cached=bool(facts.get("runtime_cached")),
                preferred_agent=candidate.agent_id == requirements.get("preferred_agent_id"),
                active_attempts=int(facts.get("active_attempts") or 0),
            )
            score, components = calculate_candidate_score(components_input, weights)
            ranked.append(candidate.with_score(score, components))
        return sorted(ranked, key=lambda item: (-item.score, item.agent_id, item.agent_instance_id or ""))


class SelectBestAgent:
    def execute(self, candidates: list[DispatchCandidate]) -> DispatchCandidate | None:
        for candidate in candidates:
            if candidate.eligible:
                return candidate
        return None


def _task_requirements(task: TaskExecutionDTO, automation_versions: AutomationVersionReader) -> dict[str, Any]:
    if task.requirements_snapshot:
        version = automation_versions.get_published_snapshot(task.automation_version_id)
        return _enrich_requirements({**task.requirements_snapshot, "task_execution_id": task.id, "execution_id": task.execution_id}, version)
    version = automation_versions.get_published_snapshot(task.automation_version_id)
    if version is None:
        raise ValueError("AutomationVersion snapshot is unavailable for scheduling.")
    return _requirements_from_version(version, task)


def _requirements_from_version(version: AutomationVersionSnapshotDTO, task: TaskExecutionDTO) -> dict[str, Any]:
    return _enrich_requirements(
        {
            "automation_version_id": version.automation_version_id,
            "runtime_version_id": version.runtime_version_id,
            "package_id": version.package_id,
            "execution_id": task.execution_id,
            "task_execution_id": task.id,
            "execution_mode": version.execution_mode,
            "required_capabilities": version.required_capabilities,
            "resource_requirements": version.resources,
            "exclusive_resources": version.exclusive_resources,
            "timeout_policy": version.timeout_policy,
            "retry_policy": version.retry_policy,
            "priority": task.priority,
            "runtime": {"id": version.runtime_id, "version": version.runtime_version},
            "package": {
                "id": version.package_id,
                "download_url": version.package_download_url,
                "sha256": version.package_sha256,
                "size_bytes": version.package_size_bytes,
            },
            "required_pools": version.required_pools,
        },
        version,
    )


def _enrich_requirements(requirements: dict[str, Any], version: AutomationVersionSnapshotDTO | None) -> dict[str, Any]:
    if version is None:
        return requirements
    package = {
        "id": version.package_id,
        "download_url": version.package_download_url,
        "sha256": version.package_sha256,
        "size_bytes": version.package_size_bytes,
        **(requirements.get("package") if isinstance(requirements.get("package"), dict) else {}),
    }
    if not package.get("download_url"):
        package["download_url"] = version.package_download_url
    return {
        **requirements,
        "automation_id": version.automation_id,
        "automation_key": version.automation_key,
        "automation_name": version.automation_name,
        "automation_version": version.version,
        "package": package,
        "resources": requirements.get("resources") or requirements.get("resource_requirements") or version.resources,
        "capabilities": requirements.get("capabilities") or requirements.get("required_capabilities") or version.required_capabilities,
    }


def _rejected_agent_ids(attempts: ExecutionAttemptRepository, task: TaskExecutionDTO) -> set[str]:
    return {attempt.agent_id for attempt in attempts.list_for_execution(task.execution_id) if attempt.task_execution_id == task.id and attempt.status == "rejected"}


def _required_capabilities(requirements: dict[str, Any]) -> list[Any]:
    return list(requirements.get("required_capabilities") or [])


def _required_pools(requirements: dict[str, Any]) -> list[str]:
    pools = requirements.get("required_pools")
    if isinstance(pools, list) and pools:
        return [str(item) for item in pools]
    mode = requirements.get("execution_mode")
    if mode == "interactive":
        return ["interactive"]
    if mode == "browser":
        return ["browser"]
    return ["background"]


def _resource_requirements(requirements: dict[str, Any]) -> dict[str, int]:
    raw = requirements.get("resource_requirements") if isinstance(requirements.get("resource_requirements"), dict) else requirements.get("resources")
    raw = raw if isinstance(raw, dict) else {}
    return {
        "cpu_units": _positive_int(raw.get("cpu_units"), 1),
        "memory_mb": _positive_int(raw.get("memory_mb"), 512),
        "disk_mb": _positive_int(raw.get("disk_mb"), 100),
    }


def _exclusive_resources(requirements: dict[str, Any]) -> list[Any]:
    return list(requirements.get("exclusive_resources") or requirements.get("resource_locks") or [])


def _timeout_policy(requirements: dict[str, Any]) -> dict[str, Any]:
    return requirements.get("timeout_policy") if isinstance(requirements.get("timeout_policy"), dict) else {}


def _scheduler_config(requirements: dict[str, Any]) -> dict[str, Any]:
    config = requirements.get("scheduler") if isinstance(requirements.get("scheduler"), dict) else {}
    return config


def _scheduling_backoff(attempts: int) -> timedelta:
    sequence = [5, 15, 30, 60, 120, 300]
    return timedelta(seconds=sequence[min(max(attempts, 0), len(sequence) - 1)])


def _execution_offer_payload(offer, task: TaskExecutionDTO, requirements: dict[str, Any]) -> dict[str, Any]:
    offer_ttl_seconds = max(int((_naive(offer.expires_at) - _naive(offer.offered_at)).total_seconds()), 0)
    return {
        "execution_offer_id": offer.id,
        "execution_id": task.execution_id,
        "execution_attempt_id": offer.execution_attempt_id,
        "task_execution_id": task.id,
        "agent_id": offer.agent_id,
        "agent_instance_id": offer.agent_instance_id,
        "automation_id": str(requirements.get("automation_id") or "") or None,
        "automation_key": requirements.get("automation_key"),
        "automation_name": requirements.get("automation_name"),
        "automation_version": requirements.get("automation_version"),
        "automation_version_id": str(task.automation_version_id),
        "execution_mode": requirements.get("execution_mode"),
        "runtime": requirements.get("runtime") or {},
        "package": requirements.get("package") or {},
        "input": {"parameters": task.parameters},
        "resources": _resource_requirements(requirements),
        "capabilities": _required_capabilities(requirements),
        "required_capabilities": _required_capabilities(requirements),
        "required_pools": _required_pools(requirements),
        "resource_locks": _exclusive_resources(requirements),
        "reservation_ttl_seconds": offer_ttl_seconds,
        "expires_at": offer.expires_at.isoformat(),
    }


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


def _offer_to_dto(offer: ExecutionOffer):
    from modules.orchestration.application.dto import ExecutionOfferDTO

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
        task_execution_id=reservation.task_execution_id,
        units=reservation.units,
        reserved_at=reservation.reserved_at,
        activated_at=reservation.activated_at,
        release_reason=reservation.release_reason,
    )


def _lock_to_dto(lock: ResourceLock):
    from modules.dispatch.application.dto import ResourceLockDTO

    return ResourceLockDTO(
        id=lock.id,
        resource_key=lock.resource_key,
        normalized_key=lock.normalized_key,
        scope=lock.scope,
        agent_id=lock.agent_id,
        execution_attempt_id=lock.execution_attempt_id,
        status=lock.status.value,
        acquired_at=lock.acquired_at,
        expires_at=lock.expires_at,
        released_at=lock.released_at,
        release_reason=lock.release_reason,
    )


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
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
