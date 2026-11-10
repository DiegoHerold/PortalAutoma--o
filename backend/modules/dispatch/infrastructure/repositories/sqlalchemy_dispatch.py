from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from infrastructure.storage import get_package_storage
from modules.catalog.infrastructure.orm.models import (
    AutomationManifestRecord,
    AutomationPackageRecord,
    CatalogAutomationRecord as Automation,
    CatalogAutomationVersionRecord as AutomationVersion,
    RuntimeRecord,
    RuntimeVersionRecord,
)
from modules.storage.infrastructure.orm.models import StoredObjectRecord
from modules.dispatch.domain.errors import AgentSelectionError
from modules.dispatch.domain.policies import required_pool_for_execution_mode
from modules.dispatch.infrastructure.orm.models import ExecutionOfferRecord, ResourceReservationRecord
from modules.fleet.infrastructure.repositories import (
    SqlAlchemyAgentCapabilityRepository,
    SqlAlchemyAgentInstanceRepository,
    SqlAlchemyAgentPoolRepository,
    SqlAlchemyAgentRepository,
    SqlAlchemyAgentResourceSnapshotRepository,
    SqlAlchemyInteractiveSessionRepository,
)
from modules.orchestration.application.dto import (
    AgentSelectionDTO,
    AgentSelectionRequestDTO,
    AutomationVersionSnapshotDTO,
    ExecutionOfferDTO,
    ResourceReservationDTO,
)
from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord, TaskExecutionRecord


class SqlAlchemyExecutionOfferRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        row = ExecutionOfferRecord(**_offer_dict(offer), commit_token_hash=commit_token_hash)
        self.db.add(row)
        self.db.flush()
        return _offer_to_dto(row)

    def save(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        row = self.db.get(ExecutionOfferRecord, offer.id)
        if row is None:
            return self.add(offer, commit_token_hash=commit_token_hash)
        for key, value in _offer_dict(offer).items():
            setattr(row, key, value)
        if commit_token_hash is not None:
            row.commit_token_hash = commit_token_hash
        self.db.add(row)
        self.db.flush()
        return _offer_to_dto(row)

    def get(self, offer_id: str) -> ExecutionOfferDTO | None:
        row = self.db.get(ExecutionOfferRecord, offer_id)
        return _offer_to_dto(row) if row else None

    def current_for_attempt(self, execution_attempt_id: str) -> ExecutionOfferDTO | None:
        row = self.db.scalar(
            select(ExecutionOfferRecord)
            .where(ExecutionOfferRecord.execution_attempt_id == execution_attempt_id)
            .order_by(ExecutionOfferRecord.offered_at.desc())
            .limit(1)
        )
        return _offer_to_dto(row) if row else None

    def list_for_attempt(self, execution_attempt_id: str) -> list[ExecutionOfferDTO]:
        rows = self.db.scalars(
            select(ExecutionOfferRecord)
            .where(ExecutionOfferRecord.execution_attempt_id == execution_attempt_id)
            .order_by(ExecutionOfferRecord.offered_at.desc())
        ).all()
        return [_offer_to_dto(row) for row in rows]

    def current_for_execution(self, execution_id: str) -> ExecutionOfferDTO | None:
        row = self.db.scalar(
            select(ExecutionOfferRecord)
            .join(ExecutionAttemptRecord, ExecutionAttemptRecord.id == ExecutionOfferRecord.execution_attempt_id)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .where(TaskExecutionRecord.execution_id == execution_id)
            .order_by(ExecutionOfferRecord.offered_at.desc())
            .limit(1)
        )
        return _offer_to_dto(row) if row else None

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ExecutionOfferDTO]:
        rows = self.db.scalars(
            select(ExecutionOfferRecord)
            .where(ExecutionOfferRecord.status.in_(["pending", "accepted"]), ExecutionOfferRecord.expires_at <= now)
            .order_by(ExecutionOfferRecord.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_offer_to_dto(row) for row in rows]


class SqlAlchemyOfferReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def reserve(self, reservation: ResourceReservationDTO) -> ResourceReservationDTO:
        row = ResourceReservationRecord(**_reservation_dict(reservation))
        self.db.add(row)
        self.db.flush()
        return _reservation_to_dto(row)

    def release_for_offer(self, offer_id: str, now: datetime) -> None:
        rows = self.db.scalars(
            select(ResourceReservationRecord)
            .where(ResourceReservationRecord.execution_offer_id == offer_id, ResourceReservationRecord.status.in_(["pending", "active", "reserved", "converted"]))
            .with_for_update()
        ).all()
        for row in rows:
            row.status = "released"
            row.released_at = now
            row.release_reason = "offer_released"
            self.db.add(row)
        self.db.flush()

    def convert_for_offer(self, offer_id: str, now: datetime) -> None:
        rows = self.db.scalars(
            select(ResourceReservationRecord)
            .where(ResourceReservationRecord.execution_offer_id == offer_id, ResourceReservationRecord.status.in_(["pending", "reserved"]))
            .with_for_update()
        ).all()
        for row in rows:
            row.status = "active"
            row.activated_at = now
            row.converted_at = now
            self.db.add(row)
        self.db.flush()

    def list_for_offer(self, offer_id: str) -> list[ResourceReservationDTO]:
        rows = self.db.scalars(
            select(ResourceReservationRecord)
            .where(ResourceReservationRecord.execution_offer_id == offer_id)
            .order_by(ResourceReservationRecord.created_at)
        ).all()
        return [_reservation_to_dto(row) for row in rows]

    def list_for_attempt(self, execution_attempt_id: str) -> list[ResourceReservationDTO]:
        rows = self.db.scalars(
            select(ResourceReservationRecord)
            .where(ResourceReservationRecord.execution_attempt_id == execution_attempt_id)
            .order_by(ResourceReservationRecord.created_at)
        ).all()
        return [_reservation_to_dto(row) for row in rows]

    def release_for_attempt(self, execution_attempt_id: str, now: datetime, reason: str) -> None:
        rows = self.db.scalars(
            select(ResourceReservationRecord)
            .where(ResourceReservationRecord.execution_attempt_id == execution_attempt_id, ResourceReservationRecord.status.in_(["pending", "active", "reserved", "converted"]))
            .with_for_update()
        ).all()
        for row in rows:
            row.status = "released"
            row.released_at = now
            row.release_reason = reason
            self.db.add(row)
        self.db.flush()

    def active_units(self, agent_id: str, pool_type: str) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(ResourceReservationRecord.units), 0)).where(
                    ResourceReservationRecord.agent_id == agent_id,
                    ResourceReservationRecord.pool_type == pool_type,
                    ResourceReservationRecord.status.in_(["pending", "active", "reserved", "converted"]),
                )
            )
            or 0
        )


class SqlAlchemyAutomationVersionReader:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_published_snapshot(self, automation_version_id: int) -> AutomationVersionSnapshotDTO | None:
        version = self.db.get(AutomationVersion, automation_version_id)
        if version is None or version.status != "published":
            return None
        automation = self.db.get(Automation, version.automation_id)
        if automation is None:
            return None
        package = self._package(version)
        runtime_version = self._runtime_version(version)
        if package is None or runtime_version is None or runtime_version.status != "published":
            return None
        runtime = self.db.get(RuntimeRecord, runtime_version.runtime_id)
        manifest = self._manifest(version)
        execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
        resources = manifest.get("resources") if isinstance(manifest.get("resources"), dict) else {}
        capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
        mode = str(execution.get("mode") or "background")
        required_pool = required_pool_for_execution_mode(mode)
        return AutomationVersionSnapshotDTO(
            automation_id=automation.id,
            automation_key=automation.key,
            automation_name=automation.name,
            automation_version_id=version.id,
            version=version.version,
            status=version.status,
            runtime_id=runtime.key if runtime else version.runtime_id,
            runtime_version=runtime_version.version,
            runtime_version_id=runtime_version.id,
            package_id=package.id,
            package_sha256=package.sha256,
            package_size_bytes=package.size_bytes,
            package_download_url=self._package_download_url(package),
            manifest=manifest,
            execution_mode=mode,
            timeout_seconds=_positive_int(execution.get("timeout_seconds"), 300),
            resources={
                "cpu_units": _positive_int(resources.get("cpu_units"), 1),
                "memory_mb": _positive_int(resources.get("memory_mb"), 512),
                "disk_mb": _positive_int(resources.get("disk_mb"), 100),
            },
            required_capabilities=list(capabilities.get("required") or []),
            required_pools=[required_pool],
            exclusive_resources=list(manifest.get("exclusive_resources") or []),
            retry_policy=_retry_policy(manifest),
            timeout_policy=_timeout_policy(manifest, _positive_int(execution.get("timeout_seconds"), 300)),
        )

    def _package(self, version: AutomationVersion) -> AutomationPackageRecord | None:
        if version.package_id:
            row = self.db.get(AutomationPackageRecord, version.package_id)
            if row is not None and row.status == "published":
                return row
        return self.db.scalar(
            select(AutomationPackageRecord)
            .where(
                AutomationPackageRecord.automation_version_id == version.id,
                AutomationPackageRecord.status == "published",
            )
            .order_by(AutomationPackageRecord.published_at.desc().nullslast(), AutomationPackageRecord.created_at.desc())
            .limit(1)
        )

    def _package_download_url(self, package: AutomationPackageRecord) -> str | None:
        stored = self.db.get(StoredObjectRecord, package.stored_object_id)
        if stored is None or stored.deleted_at is not None:
            return None
        return get_package_storage().get_download_url(stored.bucket, stored.object_key, expires_in_seconds=900)

    def _runtime_version(self, version: AutomationVersion) -> RuntimeVersionRecord | None:
        if version.runtime_version_id:
            row = self.db.get(RuntimeVersionRecord, version.runtime_version_id)
            if row is not None:
                return row
        query = (
            select(RuntimeVersionRecord)
            .join(RuntimeRecord, RuntimeRecord.id == RuntimeVersionRecord.runtime_id)
            .where(RuntimeRecord.key == version.runtime_id, RuntimeVersionRecord.status == "published")
        )
        if version.runtime_version:
            query = query.where(RuntimeVersionRecord.version == version.runtime_version)
        return self.db.scalar(query.order_by(RuntimeVersionRecord.published_at.desc().nullslast()).limit(1))

    def _manifest(self, version: AutomationVersion) -> dict[str, Any]:
        if version.manifest_id:
            row = self.db.get(AutomationManifestRecord, version.manifest_id)
            if row is not None:
                return dict(row.normalized_content or {})
        return dict(version.manifest or {})


class SimpleAgentSelectionAdapter:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.agents = SqlAlchemyAgentRepository(db)
        self.instances = SqlAlchemyAgentInstanceRepository(db)
        self.snapshots = SqlAlchemyAgentResourceSnapshotRepository(db)
        self.capabilities = SqlAlchemyAgentCapabilityRepository(db)
        self.pools = SqlAlchemyAgentPoolRepository(db)
        self.sessions = SqlAlchemyInteractiveSessionRepository(db)

    def select(self, request: AgentSelectionRequestDTO) -> AgentSelectionDTO:
        candidates = [self.agents.get(request.preferred_agent_id)] if request.preferred_agent_id else self.agents.list()
        reasons: list[str] = []
        for agent in [item for item in candidates if item is not None]:
            ok, reason = self._compatible(agent, request)
            if ok:
                current = self.instances.get_current(agent.id)
                if current is None:
                    continue
                return AgentSelectionDTO(
                    agent_id=agent.id,
                    agent_instance_id=current.id,
                    worker_id=agent.worker_id,
                    reason=reason,
                    pools=agent.pools,
                )
            reasons.append(f"{agent.id}: {reason}")
        raise AgentSelectionError("; ".join(reasons) or "No compatible Agent found.")

    def get_agent_summary(self, agent_id: str) -> dict[str, Any] | None:
        agent = self.agents.get(agent_id)
        if agent is None:
            return None
        return {
            "id": agent.id,
            "name": agent.name,
            "hostname": agent.hostname,
            "worker_id": agent.worker_id,
            "connectivity_status": agent.connectivity_status,
            "administrative_status": agent.administrative_status,
            "health_status": agent.health_status,
            "occupancy_status": agent.occupancy_status,
            "pools": agent.pools,
        }

    def _compatible(self, agent, request: AgentSelectionRequestDTO) -> tuple[bool, str]:
        now = datetime.now(UTC)
        if not agent.enabled:
            return False, "agent_disabled"
        if agent.administrative_status not in {"enabled"}:
            return False, f"administrative_status={agent.administrative_status}"
        if agent.connectivity_status != "online":
            return False, f"connectivity_status={agent.connectivity_status}"
        current = self.instances.get_current(agent.id)
        if current is None:
            return False, "missing_current_instance"
        protocol = current.negotiated_protocol_version or agent.protocol_version
        if protocol != "1.0":
            return False, "protocol_incompatible"
        snapshot = self.snapshots.latest_for_agent(agent.id)
        if snapshot is None or (snapshot.expires_at is not None and _naive(snapshot.expires_at) <= now):
            return False, "snapshot_expired"
        capability_rows = self.capabilities.list_current(agent.id)
        capability_map = {item.key: item for item in capability_rows if item.status in {"available", "active", "ok"}}
        runtime_keys = [f"runtime.{request.automation_version.runtime_id}", f"runtime:{request.automation_version.runtime_id}"]
        declared_runtime_caps = [key for key in capability_map if key.startswith("runtime.") or key.startswith("runtime:")]
        if declared_runtime_caps and not any(key in capability_map for key in runtime_keys):
            return False, "runtime_incompatible"
        for requirement in request.required_capabilities:
            key = requirement.get("key") if isinstance(requirement, dict) else None
            if key and key not in capability_map:
                return False, f"capability_missing:{key}"
        if request.execution_mode == "interactive":
            session = self.sessions.latest_for_agent(agent.id)
            if session is None or session.available is not True:
                return False, "interactive_session_unavailable"
            if session.locked is True:
                return False, "interactive_session_locked"
            if session.expires_at is not None and _naive(session.expires_at) <= now:
                return False, "interactive_session_expired"
        pools = {pool.pool_type: pool for pool in self.pools.list_current(agent.id)}
        for pool_type in request.required_pools:
            pool = pools.get(pool_type)
            if pool is None or pool.available <= 0:
                return False, f"pool_unavailable:{pool_type}"
        return True, "explicit_agent_compatible" if request.preferred_agent_id else "first_compatible_agent"


def _offer_dict(offer: ExecutionOfferDTO) -> dict[str, Any]:
    return {
        "id": offer.id,
        "execution_attempt_id": offer.execution_attempt_id,
        "agent_id": offer.agent_id,
        "agent_instance_id": offer.agent_instance_id,
        "status": offer.status,
        "requirements_snapshot": offer.requirements_snapshot or {},
        "offered_at": offer.offered_at,
        "expires_at": offer.expires_at,
        "responded_at": offer.responded_at,
        "accepted_at": offer.accepted_at,
        "committed_at": offer.committed_at,
        "rejection_code": offer.rejection_code,
        "rejection_details": offer.rejection_details,
        "correlation_id": offer.correlation_id,
        "commit_token_expires_at": offer.commit_token_expires_at,
    }


def _offer_to_dto(row: ExecutionOfferRecord) -> ExecutionOfferDTO:
    return ExecutionOfferDTO(
        id=row.id,
        execution_attempt_id=row.execution_attempt_id,
        agent_id=row.agent_id,
        agent_instance_id=row.agent_instance_id,
        status=row.status,
        requirements_snapshot=row.requirements_snapshot or {},
        offered_at=row.offered_at,
        expires_at=row.expires_at,
        responded_at=row.responded_at,
        accepted_at=row.accepted_at,
        committed_at=row.committed_at,
        rejection_code=row.rejection_code,
        rejection_details=row.rejection_details,
        correlation_id=row.correlation_id,
        commit_token_expires_at=row.commit_token_expires_at,
    )


def _reservation_to_dto(row: ResourceReservationRecord) -> ResourceReservationDTO:
    return ResourceReservationDTO(
        id=row.id,
        execution_offer_id=row.execution_offer_id,
        execution_attempt_id=row.execution_attempt_id,
        agent_id=row.agent_id,
        agent_instance_id=row.agent_instance_id,
        pool_type=row.pool_type,
        quantity=row.quantity,
        status=row.status,
        expires_at=row.expires_at,
        created_at=row.created_at,
        released_at=row.released_at,
        converted_at=row.converted_at,
        task_execution_id=row.task_execution_id,
        units=row.units,
        reserved_at=row.reserved_at,
        activated_at=row.activated_at,
        release_reason=row.release_reason,
    )


def _reservation_dict(reservation: ResourceReservationDTO) -> dict[str, Any]:
    units = getattr(reservation, "units", None) or getattr(reservation, "quantity", None) or 1
    reserved_at = getattr(reservation, "reserved_at", None) or getattr(reservation, "created_at")
    activated_at = getattr(reservation, "activated_at", None) or getattr(reservation, "converted_at", None)
    return {
        "id": reservation.id,
        "task_execution_id": getattr(reservation, "task_execution_id", None),
        "execution_offer_id": reservation.execution_offer_id,
        "execution_attempt_id": reservation.execution_attempt_id,
        "agent_id": reservation.agent_id,
        "agent_instance_id": reservation.agent_instance_id,
        "pool_type": reservation.pool_type,
        "quantity": units,
        "units": units,
        "status": reservation.status,
        "expires_at": reservation.expires_at,
        "created_at": getattr(reservation, "created_at", None) or reserved_at,
        "reserved_at": reserved_at,
        "released_at": reservation.released_at,
        "converted_at": getattr(reservation, "converted_at", None) or activated_at,
        "activated_at": activated_at,
        "release_reason": getattr(reservation, "release_reason", None),
    }


def _positive_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value > 0 else default


def _retry_policy(manifest: dict[str, Any]) -> dict[str, Any]:
    policy = manifest.get("retry_policy") if isinstance(manifest.get("retry_policy"), dict) else {}
    legacy = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
    max_attempts = _positive_int(policy.get("max_attempts"), 0)
    if max_attempts <= 0:
        max_retries = _positive_int(policy.get("max_retries"), _positive_int(legacy.get("max_retries"), 0))
        max_attempts = max_retries + 1
    return {
        "max_attempts": max_attempts,
        "initial_delay_seconds": _positive_int(policy.get("initial_delay_seconds"), 5),
        "max_delay_seconds": _positive_int(policy.get("max_delay_seconds"), 300),
        "backoff_multiplier": policy.get("backoff_multiplier") if isinstance(policy.get("backoff_multiplier"), (int, float)) and policy.get("backoff_multiplier") > 0 else 2,
        "retryable_error_codes": list(policy.get("retryable_error_codes") or []),
        "non_retryable_error_codes": list(policy.get("non_retryable_error_codes") or []),
        "retry_on_lost": bool(policy.get("retry_on_lost", True)),
        "retry_on_timeout": bool(policy.get("retry_on_timeout", False)),
        "retry_on_agent_rejection": bool(policy.get("retry_on_agent_rejection", True)),
    }


def _timeout_policy(manifest: dict[str, Any], execution_timeout_seconds: int) -> dict[str, Any]:
    policy = manifest.get("timeout_policy") if isinstance(manifest.get("timeout_policy"), dict) else {}
    execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
    return {
        "queue_timeout_seconds": _positive_int(policy.get("queue_timeout_seconds"), 300),
        "offer_timeout_seconds": _positive_int(policy.get("offer_timeout_seconds"), 60),
        "preparation_timeout_seconds": _positive_int(policy.get("preparation_timeout_seconds"), 300),
        "execution_timeout_seconds": _positive_int(policy.get("execution_timeout_seconds"), execution_timeout_seconds),
        "graceful_cancel_seconds": _positive_int(policy.get("graceful_cancel_seconds"), _positive_int(execution.get("graceful_cancellation_seconds"), 30)),
        "force_cancel_seconds": _positive_int(policy.get("force_cancel_seconds"), 120),
        "lease_duration_seconds": _positive_int(policy.get("lease_duration_seconds"), 600),
        "lease_grace_seconds": _positive_int(policy.get("lease_grace_seconds"), 60),
    }


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
