from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.worker import Worker
from modules.dispatch.infrastructure.orm.models import AgentCommandRecord
from modules.fleet.application.dto import (
    AgentCommandDTO,
    AgentConfigurationDTO,
    AgentCredentialDTO,
    AgentDTO,
    AgentDiagnosticDTO,
    AgentInstanceDTO,
    AgentPoolDTO,
    CapabilityDTO,
    InteractiveSessionDTO,
    MachineProfileDTO,
    RegistrationTokenDTO,
    ResourceSnapshotDTO,
)
from modules.fleet.infrastructure.orm.models import (
    AgentCapabilityRecord,
    AgentConfigurationRecord,
    AgentConnectionRecord,
    AgentCredentialRecord,
    AgentDiagnosticRecord,
    AgentInstanceRecord,
    AgentMachineProfileRecord,
    AgentPoolRecord,
    AgentRecord,
    AgentRegistrationTokenRecord,
    AgentResourceSnapshotRecord,
    InteractiveSessionSnapshotRecord,
)
from modules.telemetry.infrastructure.orm.models import OutboxMessageRecord


class SqlAlchemyFleetTransaction:
    def __init__(self, db: Session) -> None:
        self.db = db

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyFleetOutbox:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append_event(self, event_type: str, aggregate_id: str, payload: dict[str, Any]) -> None:
        self.db.add(
            OutboxMessageRecord(
                id=str(uuid4()),
                topic="fleet.events",
                message_type=event_type,
                aggregate_type="agent",
                aggregate_id=aggregate_id,
                payload=payload,
                status="pending",
                correlation_id=payload.get("correlation_id"),
                causation_id=payload.get("causation_id"),
            )
        )
        self.db.flush()


class SqlAlchemyAgentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, agent: AgentDTO) -> AgentDTO:
        worker_id = agent.worker_id
        if worker_id is None:
            worker = Worker(
                name=agent.name,
                hostname=agent.hostname,
                agent_id=agent.id,
                machine_id=agent.local_identity,
                agent_version=agent.current_version,
                status=_worker_status(agent),
                max_concurrency=1,
                is_active=agent.enabled,
            )
            self.db.add(worker)
            self.db.flush()
            worker_id = worker.id
        row = AgentRecord(
            id=agent.id,
            worker_id=worker_id,
            name=agent.name,
            hostname=agent.hostname,
            enabled=agent.enabled,
            connectivity_status=agent.connectivity_status,
            administrative_status=agent.administrative_status,
            health_status=agent.health_status,
            occupancy_status=agent.occupancy_status,
            current_version=agent.current_version,
            desired_version=agent.desired_version,
            protocol_version=agent.protocol_version,
            local_identity=agent.local_identity,
            machine_fingerprint=agent.machine_fingerprint,
            metadata_json={},
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            last_seen_at=agent.last_seen_at,
            disabled_at=agent.disabled_at,
        )
        self.db.add(row)
        self.db.flush()
        return self._to_dto(row)

    def save(self, agent: AgentDTO) -> AgentDTO:
        row = self.db.get(AgentRecord, agent.id)
        if row is None:
            return self.add(agent)
        _copy_agent(agent, row)
        self.db.add(row)
        self._sync_worker(row)
        self.db.flush()
        return self._to_dto(row)

    def get(self, agent_id: str) -> AgentDTO | None:
        row = self.db.get(AgentRecord, agent_id)
        return self._to_dto(row) if row else None

    def get_by_local_identity(self, local_identity: str) -> AgentDTO | None:
        row = self.db.scalar(select(AgentRecord).where(AgentRecord.local_identity == local_identity))
        return self._to_dto(row) if row else None

    def get_by_machine_fingerprint(self, machine_fingerprint: str) -> AgentDTO | None:
        row = self.db.scalar(select(AgentRecord).where(AgentRecord.machine_fingerprint == machine_fingerprint))
        return self._to_dto(row) if row else None

    def get_by_worker_id(self, worker_id: int) -> AgentDTO | None:
        row = self.db.scalar(select(AgentRecord).where(AgentRecord.worker_id == worker_id))
        return self._to_dto(row) if row else None

    def list(self) -> list[AgentDTO]:
        return [self._to_dto(row) for row in self.db.scalars(select(AgentRecord).order_by(AgentRecord.name)).all()]

    def _to_dto(self, row: AgentRecord) -> AgentDTO:
        snapshot = _latest_snapshot(self.db, row.id)
        session = _latest_session(self.db, row.id)
        pools = _current_pools(self.db, row.id)
        return AgentDTO(
            id=row.id,
            name=row.name,
            hostname=row.hostname,
            enabled=row.enabled,
            connectivity_status=row.connectivity_status,
            administrative_status=row.administrative_status,
            health_status=row.health_status,
            occupancy_status=row.occupancy_status,
            current_version=row.current_version,
            desired_version=row.desired_version,
            protocol_version=row.protocol_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_seen_at=row.last_seen_at,
            disabled_at=row.disabled_at,
            local_identity=row.local_identity,
            machine_fingerprint=row.machine_fingerprint,
            worker_id=row.worker_id,
            cpu_percentage=snapshot.cpu_usage_percentage if snapshot else None,
            memory_percentage=snapshot.memory_usage_percentage if snapshot else None,
            disk_free_mb=snapshot.disk_free_mb if snapshot else None,
            interactive_session=_session_dict(session) if session else None,
            pools={pool.pool_type: _pool_dict(pool) for pool in pools},
            alerts=[],
        )

    def _sync_worker(self, row: AgentRecord) -> None:
        if row.worker_id is None:
            return
        worker = self.db.get(Worker, row.worker_id)
        if worker is None:
            return
        worker.name = row.name
        worker.hostname = row.hostname
        worker.agent_id = row.id
        worker.machine_id = row.local_identity
        worker.agent_version = row.current_version
        worker.status = _worker_status_row(row)
        worker.last_heartbeat_at = row.last_seen_at
        worker.is_active = row.enabled
        latest_profile = self.db.scalar(select(AgentMachineProfileRecord).where(AgentMachineProfileRecord.agent_id == row.id).order_by(AgentMachineProfileRecord.observed_at.desc()).limit(1))
        if latest_profile:
            worker.os = latest_profile.operating_system
            worker.architecture = latest_profile.architecture
        worker.last_payload_json = {"agent": {"id": row.id, "connectivity_status": row.connectivity_status, "administrative_status": row.administrative_status, "health_status": row.health_status}}
        capabilities = list(self.db.scalars(select(AgentCapabilityRecord).where(AgentCapabilityRecord.agent_id == row.id, AgentCapabilityRecord.is_current.is_(True))).all())
        worker.capabilities_json = [{"key": item.key, "status": item.status, "version": item.version, "attributes": item.attributes_json} for item in capabilities]
        pool_total = sum(pool.effective_total for pool in _current_pools(self.db, row.id))
        if pool_total > 0:
            worker.max_concurrency = pool_total
        self.db.add(worker)


class SqlAlchemyAgentInstanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, instance: AgentInstanceDTO) -> AgentInstanceDTO:
        row = AgentInstanceRecord(**_instance_dict(instance))
        self.db.add(row)
        self.db.flush()
        return _instance_to_dto(row)

    def save(self, instance: AgentInstanceDTO) -> AgentInstanceDTO:
        row = self.db.get(AgentInstanceRecord, instance.id)
        if row is None:
            return self.add(instance)
        for key, value in _instance_dict(instance).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _instance_to_dto(row)

    def get(self, instance_id: str) -> AgentInstanceDTO | None:
        row = self.db.get(AgentInstanceRecord, instance_id)
        return _instance_to_dto(row) if row else None

    def get_current(self, agent_id: str) -> AgentInstanceDTO | None:
        row = self.db.scalar(
            select(AgentInstanceRecord)
            .where(AgentInstanceRecord.agent_id == agent_id, AgentInstanceRecord.disconnected_at.is_(None))
            .order_by(AgentInstanceRecord.connected_at.desc().nullslast(), AgentInstanceRecord.created_at.desc())
            .limit(1)
        )
        return _instance_to_dto(row) if row else None

    def list_for_agent(self, agent_id: str) -> list[AgentInstanceDTO]:
        return [_instance_to_dto(row) for row in self.db.scalars(select(AgentInstanceRecord).where(AgentInstanceRecord.agent_id == agent_id).order_by(AgentInstanceRecord.created_at.desc())).all()]

    def disconnect_active_for_agent(self, agent_id: str, now: datetime, reason: str) -> None:
        rows = self.db.scalars(select(AgentInstanceRecord).where(AgentInstanceRecord.agent_id == agent_id, AgentInstanceRecord.disconnected_at.is_(None))).all()
        for row in rows:
            row.disconnected_at = now
            row.shutdown_reason = reason
            self.db.add(row)
        self.db.flush()


class SqlAlchemyAgentRegistrationTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, token: RegistrationTokenDTO, token_hash: str) -> RegistrationTokenDTO:
        row = AgentRegistrationTokenRecord(
            id=token.id,
            token_hash=token_hash,
            status=token.status,
            expires_at=token.expires_at,
            used_at=token.used_at,
            used_by_agent_id=token.used_by_agent_id,
            created_by=token.created_by,
            created_at=token.created_at,
            revoked_at=token.revoked_at,
            metadata_json=token.metadata,
        )
        self.db.add(row)
        self.db.flush()
        return _token_to_dto(row)

    def get(self, token_id: str) -> RegistrationTokenDTO | None:
        row = self.db.get(AgentRegistrationTokenRecord, token_id)
        return _token_to_dto(row) if row else None

    def get_by_hash(self, token_hash: str) -> RegistrationTokenDTO | None:
        row = self.db.scalar(select(AgentRegistrationTokenRecord).where(AgentRegistrationTokenRecord.token_hash == token_hash).with_for_update())
        return _token_to_dto(row) if row else None

    def save(self, token: RegistrationTokenDTO) -> RegistrationTokenDTO:
        row = self.db.get(AgentRegistrationTokenRecord, token.id)
        if row is None:
            raise ValueError("Registration token not found.")
        row.status = token.status
        row.used_at = token.used_at
        row.used_by_agent_id = token.used_by_agent_id
        row.revoked_at = token.revoked_at
        row.metadata_json = token.metadata
        self.db.add(row)
        self.db.flush()
        return _token_to_dto(row)


class SqlAlchemyAgentCredentialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, credential: AgentCredentialDTO, secret_hash: str) -> AgentCredentialDTO:
        row = AgentCredentialRecord(
            id=credential.id,
            agent_id=credential.agent_id,
            credential_type=credential.credential_type,
            public_identifier=credential.public_identifier,
            secret_hash=secret_hash,
            status=credential.status,
            issued_at=credential.issued_at,
            expires_at=credential.expires_at,
            last_used_at=credential.last_used_at,
            rotated_at=credential.rotated_at,
            revoked_at=credential.revoked_at,
        )
        self.db.add(row)
        self.db.flush()
        return _credential_to_dto(row, secret=credential.secret)

    def get(self, credential_id: str) -> AgentCredentialDTO | None:
        row = self.db.get(AgentCredentialRecord, credential_id)
        return _credential_to_dto(row) if row else None

    def get_by_public_identifier(self, public_identifier: str) -> tuple[AgentCredentialDTO, str] | None:
        row = self.db.scalar(select(AgentCredentialRecord).where(AgentCredentialRecord.public_identifier == public_identifier).with_for_update())
        return (_credential_to_dto(row), row.secret_hash) if row else None

    def save(self, credential: AgentCredentialDTO) -> AgentCredentialDTO:
        row = self.db.get(AgentCredentialRecord, credential.id)
        if row is None:
            raise ValueError("Agent credential not found.")
        row.status = credential.status
        row.last_used_at = credential.last_used_at
        row.rotated_at = credential.rotated_at
        row.revoked_at = credential.revoked_at
        row.expires_at = credential.expires_at
        self.db.add(row)
        self.db.flush()
        return _credential_to_dto(row)

    def active_for_agent(self, agent_id: str) -> list[AgentCredentialDTO]:
        return [_credential_to_dto(row) for row in self.db.scalars(select(AgentCredentialRecord).where(AgentCredentialRecord.agent_id == agent_id, AgentCredentialRecord.status == "active")).all()]


class SqlAlchemyAgentMachineProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, profile: MachineProfileDTO) -> MachineProfileDTO:
        row = AgentMachineProfileRecord(
            id=profile.id,
            agent_id=profile.agent_id,
            agent_instance_id=profile.agent_instance_id,
            hostname=profile.hostname,
            operating_system=profile.operating_system,
            operating_system_version=profile.operating_system_version,
            operating_system_build=profile.operating_system_build,
            architecture=profile.architecture,
            cpu_model=profile.cpu_model,
            physical_cores=profile.physical_cores,
            logical_processors=profile.logical_processors,
            total_memory_mb=profile.total_memory_mb,
            disk_volumes=profile.disk_volumes,
            network_summary=profile.network_summary,
            interactive_session_supported=profile.interactive_session_supported,
            observed_at=profile.observed_at,
            revision=profile.revision,
            expires_at=profile.expires_at,
        )
        self.db.add(row)
        self.db.flush()
        return _profile_to_dto(row)

    def latest_for_agent(self, agent_id: str) -> MachineProfileDTO | None:
        row = self.db.scalar(select(AgentMachineProfileRecord).where(AgentMachineProfileRecord.agent_id == agent_id).order_by(AgentMachineProfileRecord.observed_at.desc()).limit(1))
        return _profile_to_dto(row) if row else None


class SqlAlchemyAgentResourceSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, snapshot: ResourceSnapshotDTO) -> ResourceSnapshotDTO:
        row = AgentResourceSnapshotRecord(**snapshot.__dict__)
        self.db.add(row)
        self.db.flush()
        return _snapshot_to_dto(row)

    def latest_for_agent(self, agent_id: str) -> ResourceSnapshotDTO | None:
        row = _latest_snapshot(self.db, agent_id)
        return _snapshot_to_dto(row) if row else None


class SqlAlchemyAgentCapabilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_current(self, agent_id: str, capabilities: list[CapabilityDTO]) -> list[CapabilityDTO]:
        self.db.execute(update(AgentCapabilityRecord).where(AgentCapabilityRecord.agent_id == agent_id, AgentCapabilityRecord.is_current.is_(True)).values(is_current=False))
        rows: list[AgentCapabilityRecord] = []
        for capability in capabilities:
            row = AgentCapabilityRecord(
                id=capability.id or str(uuid4()),
                agent_id=agent_id,
                agent_instance_id=capability.agent_instance_id,
                key=capability.key,
                status=capability.status,
                version=capability.version,
                attributes_json=capability.attributes,
                source=capability.source,
                observed_at=capability.observed_at,
                expires_at=capability.expires_at,
                revision=capability.revision,
                is_current=True,
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return [_capability_to_dto(row) for row in rows]

    def list_current(self, agent_id: str) -> list[CapabilityDTO]:
        return [_capability_to_dto(row) for row in self.db.scalars(select(AgentCapabilityRecord).where(AgentCapabilityRecord.agent_id == agent_id, AgentCapabilityRecord.is_current.is_(True)).order_by(AgentCapabilityRecord.key)).all()]


class SqlAlchemyAgentConfigurationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, agent_id: str) -> AgentConfigurationDTO | None:
        row = self.db.get(AgentConfigurationRecord, agent_id)
        return _configuration_to_dto(row) if row else None

    def save(self, configuration: AgentConfigurationDTO) -> AgentConfigurationDTO:
        row = self.db.get(AgentConfigurationRecord, configuration.agent_id)
        if row is None:
            row = AgentConfigurationRecord(agent_id=configuration.agent_id)
            self.db.add(row)
        row.heartbeat_interval_seconds = configuration.heartbeat_interval_seconds
        row.stale_after_seconds = configuration.stale_after_seconds
        row.offline_after_seconds = configuration.offline_after_seconds
        row.administrator_pool_limits = configuration.administrator_pool_limits
        row.enabled_pools = configuration.enabled_pools
        row.allowlist_capabilities = configuration.allowlist_capabilities
        row.maintenance = configuration.maintenance
        row.desired_version = configuration.desired_version
        row.restrictions = configuration.restrictions
        row.updated_at = configuration.updated_at or datetime.utcnow()
        self.db.add(row)
        self.db.flush()
        return _configuration_to_dto(row)


class SqlAlchemyAgentPoolRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_current(self, agent_id: str, pools: list[AgentPoolDTO]) -> list[AgentPoolDTO]:
        self.db.execute(update(AgentPoolRecord).where(AgentPoolRecord.agent_id == agent_id, AgentPoolRecord.is_current.is_(True)).values(is_current=False))
        rows: list[AgentPoolRecord] = []
        for pool in pools:
            row = AgentPoolRecord(
                id=str(uuid4()),
                agent_id=agent_id,
                pool_type=pool.pool_type,
                recommended_total=pool.recommended_total,
                administrator_total=pool.administrator_total,
                effective_total=pool.effective_total,
                used=pool.used,
                reserved=pool.reserved,
                available=pool.available,
                observed_at=pool.observed_at,
                revision=pool.revision,
                is_current=True,
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return [_pool_to_dto(row) for row in rows]

    def list_current(self, agent_id: str) -> list[AgentPoolDTO]:
        return [_pool_to_dto(row) for row in _current_pools(self.db, agent_id)]


class SqlAlchemyInteractiveSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, snapshot: InteractiveSessionDTO) -> InteractiveSessionDTO:
        row = InteractiveSessionSnapshotRecord(
            id=str(uuid4()),
            agent_id=snapshot.agent_id,
            agent_instance_id=snapshot.agent_instance_id,
            available=snapshot.available,
            locked=snapshot.locked,
            user=snapshot.user,
            session_id=snapshot.session_id,
            session_type=snapshot.session_type,
            state=snapshot.state,
            observed_at=snapshot.observed_at,
            expires_at=snapshot.expires_at,
        )
        self.db.add(row)
        self.db.flush()
        return _interactive_to_dto(row)

    def latest_for_agent(self, agent_id: str) -> InteractiveSessionDTO | None:
        row = _latest_session(self.db, agent_id)
        return _interactive_to_dto(row) if row else None


class SqlAlchemyAgentConnectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def open(self, connection_id: str, agent_id: str, agent_instance_id: str, connected_at: datetime, protocol_version: str) -> None:
        row = AgentConnectionRecord(
            id=str(uuid4()),
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            connection_id=connection_id,
            protocol_version=protocol_version,
            status="open",
            connected_at=connected_at,
        )
        self.db.add(row)
        self.db.flush()

    def close(self, connection_id: str, disconnected_at: datetime, reason: str | None) -> None:
        row = self.db.scalar(select(AgentConnectionRecord).where(AgentConnectionRecord.connection_id == connection_id))
        if row is None:
            return
        row.status = "closed"
        row.disconnected_at = disconnected_at
        row.close_reason = reason
        self.db.add(row)
        self.db.flush()

    def close_active_for_agent(self, agent_id: str, disconnected_at: datetime, reason: str) -> None:
        rows = self.db.scalars(select(AgentConnectionRecord).where(AgentConnectionRecord.agent_id == agent_id, AgentConnectionRecord.status == "open")).all()
        for row in rows:
            row.status = "closed"
            row.disconnected_at = disconnected_at
            row.close_reason = reason
            self.db.add(row)
        self.db.flush()


class SqlAlchemyAgentDiagnosticRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, diagnostic: AgentDiagnosticDTO) -> AgentDiagnosticDTO:
        row = AgentDiagnosticRecord(**diagnostic.__dict__)
        self.db.add(row)
        self.db.flush()
        return _diagnostic_to_dto(row)

    def save_result(self, diagnostic: AgentDiagnosticDTO) -> AgentDiagnosticDTO:
        row = self.db.get(AgentDiagnosticRecord, diagnostic.id)
        if row is None:
            return self.add(diagnostic)
        for key, value in diagnostic.__dict__.items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _diagnostic_to_dto(row)

    def list_for_agent(self, agent_id: str) -> list[AgentDiagnosticDTO]:
        return [_diagnostic_to_dto(row) for row in self.db.scalars(select(AgentDiagnosticRecord).where(AgentDiagnosticRecord.agent_id == agent_id).order_by(AgentDiagnosticRecord.requested_at.desc())).all()]


class SqlAlchemyAgentCommandRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, agent_id: str, message_type: str, payload: dict[str, Any], expires_at: datetime | None = None) -> AgentCommandDTO:
        self.db.scalar(select(AgentRecord).where(AgentRecord.id == agent_id).with_for_update())
        current_sequence = self.db.scalar(select(func.max(AgentCommandRecord.command_sequence)).where(AgentCommandRecord.agent_id == agent_id)) or 0
        now = datetime.utcnow()
        row = AgentCommandRecord(
            id=f"cmd_{uuid4().hex}",
            agent_id=agent_id,
            agent_instance_id=None,
            command_sequence=current_sequence + 1,
            message_type=message_type,
            payload=payload,
            status="pending",
            created_at=now,
            available_at=now,
            expires_at=expires_at,
            attempts=0,
        )
        self.db.add(row)
        self.db.flush()
        return _command_to_dto(row)

    def pending_for_agent(self, agent_id: str, limit: int) -> list[AgentCommandDTO]:
        now = datetime.utcnow()
        rows = self.db.scalars(
            select(AgentCommandRecord)
            .where(
                AgentCommandRecord.agent_id == agent_id,
                AgentCommandRecord.status.in_(["pending", "sent"]),
                AgentCommandRecord.available_at <= now,
            )
            .order_by(AgentCommandRecord.command_sequence)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [_command_to_dto(row) for row in rows if row.expires_at is None or _naive(row.expires_at) > now]

    def mark_sent(self, command_id: str, agent_instance_id: str, sent_at: datetime) -> AgentCommandDTO | None:
        row = self.db.get(AgentCommandRecord, command_id)
        if row is None:
            return None
        row.agent_instance_id = agent_instance_id
        row.status = "sent"
        row.sent_at = sent_at
        row.attempts += 1
        self.db.add(row)
        self.db.flush()
        return _command_to_dto(row)

    def acknowledge(self, agent_id: str, command_id: str, command_sequence: int | None, status: str, acknowledged_at: datetime) -> AgentCommandDTO | None:
        query = select(AgentCommandRecord).where(AgentCommandRecord.agent_id == agent_id)
        if command_id:
            query = query.where(AgentCommandRecord.id == command_id)
        elif command_sequence is not None:
            query = query.where(AgentCommandRecord.command_sequence == command_sequence)
        else:
            return None
        row = self.db.scalar(query.with_for_update())
        if row is None:
            return None
        row.status = "acknowledged" if status in {"received", "accepted", "completed"} else "failed"
        row.acknowledged_at = acknowledged_at
        row.last_error = None if row.status == "acknowledged" else status
        self.db.add(row)
        self.db.flush()
        return _command_to_dto(row)


def _copy_agent(agent: AgentDTO, row: AgentRecord) -> None:
    row.name = agent.name
    row.hostname = agent.hostname
    row.enabled = agent.enabled
    row.connectivity_status = agent.connectivity_status
    row.administrative_status = agent.administrative_status
    row.health_status = agent.health_status
    row.occupancy_status = agent.occupancy_status
    row.current_version = agent.current_version
    row.desired_version = agent.desired_version
    row.protocol_version = agent.protocol_version
    row.local_identity = agent.local_identity
    row.machine_fingerprint = agent.machine_fingerprint
    row.updated_at = agent.updated_at or datetime.utcnow()
    row.last_seen_at = agent.last_seen_at
    row.disabled_at = agent.disabled_at


def _worker_status(agent: AgentDTO) -> str:
    if not agent.enabled or agent.administrative_status == "disabled":
        return "disabled"
    return agent.connectivity_status


def _worker_status_row(row: AgentRecord) -> str:
    if not row.enabled or row.administrative_status == "disabled":
        return "disabled"
    return row.connectivity_status


def _latest_snapshot(db: Session, agent_id: str) -> AgentResourceSnapshotRecord | None:
    return db.scalar(select(AgentResourceSnapshotRecord).where(AgentResourceSnapshotRecord.agent_id == agent_id).order_by(AgentResourceSnapshotRecord.observed_at.desc()).limit(1))


def _latest_session(db: Session, agent_id: str) -> InteractiveSessionSnapshotRecord | None:
    return db.scalar(select(InteractiveSessionSnapshotRecord).where(InteractiveSessionSnapshotRecord.agent_id == agent_id).order_by(InteractiveSessionSnapshotRecord.observed_at.desc()).limit(1))


def _current_pools(db: Session, agent_id: str) -> list[AgentPoolRecord]:
    return list(db.scalars(select(AgentPoolRecord).where(AgentPoolRecord.agent_id == agent_id, AgentPoolRecord.is_current.is_(True)).order_by(AgentPoolRecord.pool_type)).all())


def _pool_dict(pool: AgentPoolRecord) -> dict[str, Any]:
    return {
        "recommended_total": pool.recommended_total,
        "administrator_total": pool.administrator_total,
        "effective_total": pool.effective_total,
        "used": pool.used,
        "reserved": pool.reserved,
        "available": pool.available,
    }


def _session_dict(row: InteractiveSessionSnapshotRecord) -> dict[str, Any]:
    return {"available": row.available, "locked": row.locked, "user": row.user, "session_id": row.session_id, "session_type": row.session_type, "state": row.state, "observed_at": row.observed_at}


def _instance_dict(instance: AgentInstanceDTO) -> dict[str, Any]:
    return {
        "id": instance.id,
        "agent_id": instance.agent_id,
        "process_started_at": instance.process_started_at,
        "connected_at": instance.connected_at,
        "last_seen_at": instance.last_seen_at,
        "disconnected_at": instance.disconnected_at,
        "shutdown_reason": instance.shutdown_reason,
        "agent_version": instance.agent_version,
        "negotiated_protocol_version": instance.negotiated_protocol_version,
        "connection_id": instance.connection_id,
        "created_at": instance.created_at,
    }


def _instance_to_dto(row: AgentInstanceRecord) -> AgentInstanceDTO:
    return AgentInstanceDTO(**{key: getattr(row, key) for key in _instance_dict(AgentInstanceDTO("", "", datetime.utcnow(), None, None, None, None, None, None, None, None)).keys()})


def _token_to_dto(row: AgentRegistrationTokenRecord) -> RegistrationTokenDTO:
    return RegistrationTokenDTO(id=row.id, token=None, status=row.status, expires_at=row.expires_at, used_at=row.used_at, used_by_agent_id=row.used_by_agent_id, created_by=row.created_by, created_at=row.created_at, revoked_at=row.revoked_at, metadata=row.metadata_json or {})


def _credential_to_dto(row: AgentCredentialRecord, secret: str | None = None) -> AgentCredentialDTO:
    return AgentCredentialDTO(id=row.id, agent_id=row.agent_id, credential_type=row.credential_type, public_identifier=row.public_identifier, status=row.status, issued_at=row.issued_at, expires_at=row.expires_at, last_used_at=row.last_used_at, rotated_at=row.rotated_at, revoked_at=row.revoked_at, secret=secret)


def _profile_to_dto(row: AgentMachineProfileRecord) -> MachineProfileDTO:
    return MachineProfileDTO(id=row.id, agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, hostname=row.hostname, operating_system=row.operating_system, operating_system_version=row.operating_system_version, operating_system_build=row.operating_system_build, architecture=row.architecture, cpu_model=row.cpu_model, physical_cores=row.physical_cores, logical_processors=row.logical_processors, total_memory_mb=row.total_memory_mb, disk_volumes=row.disk_volumes or [], network_summary=row.network_summary or {}, interactive_session_supported=row.interactive_session_supported, observed_at=row.observed_at, revision=row.revision, expires_at=row.expires_at)


def _snapshot_to_dto(row: AgentResourceSnapshotRecord) -> ResourceSnapshotDTO:
    return ResourceSnapshotDTO(id=row.id, agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, cpu_usage_percentage=row.cpu_usage_percentage, memory_total_mb=row.memory_total_mb, memory_available_mb=row.memory_available_mb, memory_usage_percentage=row.memory_usage_percentage, disk_free_mb=row.disk_free_mb, disk_usage_percentage=row.disk_usage_percentage, process_count=row.process_count, uptime_seconds=row.uptime_seconds, observed_at=row.observed_at, revision=row.revision, expires_at=row.expires_at)


def _capability_to_dto(row: AgentCapabilityRecord) -> CapabilityDTO:
    return CapabilityDTO(id=row.id, agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, key=row.key, status=row.status, version=row.version, attributes=row.attributes_json or {}, source=row.source, observed_at=row.observed_at, expires_at=row.expires_at, revision=row.revision)


def _configuration_to_dto(row: AgentConfigurationRecord) -> AgentConfigurationDTO:
    return AgentConfigurationDTO(agent_id=row.agent_id, heartbeat_interval_seconds=row.heartbeat_interval_seconds, stale_after_seconds=row.stale_after_seconds, offline_after_seconds=row.offline_after_seconds, administrator_pool_limits=row.administrator_pool_limits or {}, enabled_pools=row.enabled_pools or [], allowlist_capabilities=row.allowlist_capabilities or [], maintenance=row.maintenance, desired_version=row.desired_version, restrictions=row.restrictions or {}, updated_at=row.updated_at)


def _pool_to_dto(row: AgentPoolRecord) -> AgentPoolDTO:
    return AgentPoolDTO(agent_id=row.agent_id, pool_type=row.pool_type, recommended_total=row.recommended_total, administrator_total=row.administrator_total, effective_total=row.effective_total, used=row.used, reserved=row.reserved, available=row.available, observed_at=row.observed_at, revision=row.revision)


def _interactive_to_dto(row: InteractiveSessionSnapshotRecord) -> InteractiveSessionDTO:
    return InteractiveSessionDTO(agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, available=row.available, locked=row.locked, user=row.user, session_id=row.session_id, session_type=row.session_type, state=row.state, observed_at=row.observed_at, expires_at=row.expires_at)


def _diagnostic_to_dto(row: AgentDiagnosticRecord) -> AgentDiagnosticDTO:
    return AgentDiagnosticDTO(id=row.id, agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, request_command_id=row.request_command_id, status=row.status, summary=row.summary, details=row.details or {}, artifact_id=row.artifact_id, requested_at=row.requested_at, completed_at=row.completed_at, error=row.error)


def _command_to_dto(row: AgentCommandRecord) -> AgentCommandDTO:
    return AgentCommandDTO(id=row.id, agent_id=row.agent_id, agent_instance_id=row.agent_instance_id, command_sequence=row.command_sequence, message_type=row.message_type, payload=row.payload, status=row.status, created_at=row.created_at, available_at=row.available_at, sent_at=row.sent_at, acknowledged_at=row.acknowledged_at, expires_at=row.expires_at, attempts=row.attempts, last_error=row.last_error)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value
