from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.worker import Worker
from app.repositories.job_repository import JobRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas.worker import WorkerCreate, WorkerRead, WorkerUpdate
from app.services.permission_service import PermissionService
from modules.fleet.application.dto import AgentDTO
from modules.fleet.application.use_cases import DisableAgent
from modules.fleet.application.use_cases._shared import default_configuration
from modules.fleet.domain.value_objects import generate_agent_id
from modules.fleet.infrastructure.adapters import build_fleet_adapters


class WorkerService:
    """
    Compatibility adapter for the old /workers API.

    Worker is no longer the official domain entity. Reads and writes are
    translated to Fleet.Agent while the legacy table remains linked through
    Agent.worker_id for the current frontend and dispatcher compatibility.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workers = WorkerRepository(db)
        self.jobs = JobRepository(db)
        self.permissions = PermissionService(db)
        self.fleet = build_fleet_adapters(db)

    def list_workers(self) -> list[WorkerRead]:
        agents = self.fleet.agents.list()
        if not agents:
            agents = [self._ensure_agent_for_worker(worker) for worker in self.workers.list_all()]
            self.db.commit()
        return [self._worker_read(agent) for agent in agents]

    def get_worker(self, worker_id: int) -> WorkerRead:
        agent = self.fleet.agents.get_by_worker_id(worker_id)
        if agent is None:
            worker = self.workers.get(worker_id)
            if worker is None:
                raise ValueError("Worker not found.")
            agent = self._ensure_agent_for_worker(worker)
            self.db.commit()
        return self._worker_read(agent)

    def get_worker_model(self, worker_id: int) -> Worker:
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        return worker

    def create_worker(self, user, payload: WorkerCreate) -> WorkerRead:
        self.permissions.ensure_admin_or_manager(user)
        now = datetime.utcnow()
        agent = AgentDTO(
            id=payload.agent_id or generate_agent_id(),
            worker_id=None,
            name=payload.name,
            hostname=payload.hostname,
            enabled=payload.is_active,
            connectivity_status=_compat_connectivity(payload.status),
            administrative_status="enabled" if payload.is_active else "disabled",
            health_status="healthy",
            occupancy_status="busy" if payload.status == "busy" else "idle",
            current_version=payload.agent_version,
            desired_version=None,
            protocol_version=None,
            created_at=now,
            updated_at=now,
            last_seen_at=payload.last_heartbeat_at if hasattr(payload, "last_heartbeat_at") else None,
            disabled_at=None if payload.is_active else now,
            local_identity=payload.machine_id,
            machine_fingerprint=payload.machine_id,
        )
        created = self.fleet.agents.add(agent)
        self.fleet.configurations.save(default_configuration(created.id))
        self.db.commit()
        return self._worker_read(created)

    def update_worker(self, user, worker_id: int, payload: WorkerUpdate) -> WorkerRead:
        self.permissions.ensure_admin_or_manager(user)
        agent = self.fleet.agents.get_by_worker_id(worker_id)
        if agent is None:
            worker = self.workers.get(worker_id)
            if worker is None:
                raise ValueError("Worker not found.")
            agent = self._ensure_agent_for_worker(worker)
        updated = self.fleet.agents.save(
            replace(
                agent,
                name=payload.name,
                hostname=payload.hostname,
                enabled=payload.is_active,
                connectivity_status=_compat_connectivity(payload.status),
                administrative_status="enabled" if payload.is_active else "disabled",
                occupancy_status="busy" if payload.status == "busy" else agent.occupancy_status,
                current_version=payload.agent_version or agent.current_version,
                local_identity=payload.machine_id or agent.local_identity,
                machine_fingerprint=payload.machine_id or agent.machine_fingerprint,
                updated_at=datetime.utcnow(),
            )
        )
        self.db.commit()
        return self._worker_read(updated)

    def delete_worker(self, user, worker_id: int) -> None:
        self.permissions.ensure_admin_or_manager(user)
        agent = self.fleet.agents.get_by_worker_id(worker_id)
        if agent is None:
            worker = self.workers.get(worker_id)
            if worker is None:
                raise ValueError("Worker not found.")
            agent = self._ensure_agent_for_worker(worker)
        DisableAgent(self.fleet.agents, self.fleet.audit, self.fleet.outbox, self.fleet.transaction).execute(
            agent.id,
            actor=self._actor(user),
            reason="disabled through legacy /workers API",
        )

    def _ensure_agent_for_worker(self, worker: Worker) -> AgentDTO:
        existing = self.fleet.agents.get(worker.agent_id) if worker.agent_id else None
        if existing is not None:
            return existing
        now = datetime.utcnow()
        agent_id = worker.agent_id or f"agt_worker_{worker.id}"
        if not worker.agent_id:
            worker.agent_id = agent_id
            self.db.add(worker)
            self.db.flush()
        return self.fleet.agents.add(
            AgentDTO(
                id=agent_id,
                worker_id=worker.id,
                name=worker.name,
                hostname=worker.hostname,
                enabled=worker.is_active,
                connectivity_status=_compat_connectivity(worker.status),
                administrative_status="enabled" if worker.is_active and worker.status != "disabled" else "disabled",
                health_status="healthy",
                occupancy_status="busy" if worker.status == "busy" else "idle",
                current_version=worker.agent_version,
                desired_version=None,
                protocol_version=None,
                created_at=getattr(worker, "created_at", None) or now,
                updated_at=getattr(worker, "updated_at", None) or now,
                last_seen_at=worker.last_heartbeat_at,
                disabled_at=None if worker.is_active else now,
                local_identity=worker.machine_id,
                machine_fingerprint=worker.machine_id,
            )
        )

    def _worker_read(self, agent: AgentDTO) -> WorkerRead:
        worker_id = agent.worker_id
        if worker_id is None:
            saved = self.fleet.agents.save(agent)
            self.db.flush()
            worker_id = saved.worker_id
            agent = saved
        active_jobs = self.jobs.count_running_by_worker(worker_id) if worker_id is not None else 0
        pools_total = sum((pool.get("effective_total") or 0) for pool in agent.pools.values())
        return WorkerRead(
            id=worker_id or 0,
            name=agent.name,
            hostname=agent.hostname,
            ip_address=None,
            agent_id=agent.id,
            machine_id=agent.local_identity,
            agent_version=agent.current_version,
            os=None,
            architecture=None,
            capabilities_json=[],
            last_payload_json={
                "agent": {
                    "connectivity_status": agent.connectivity_status,
                    "administrative_status": agent.administrative_status,
                    "health_status": agent.health_status,
                    "occupancy_status": agent.occupancy_status,
                    "interactive_session": agent.interactive_session,
                    "pools": agent.pools,
                }
            },
            status=agent.connectivity_status,
            connectivity_status=agent.connectivity_status,
            administrative_status=agent.administrative_status,
            health_status=agent.health_status,
            occupancy_status=agent.occupancy_status,
            desired_version=agent.desired_version,
            cpu_percentage=agent.cpu_percentage,
            memory_percentage=agent.memory_percentage,
            disk_free_mb=agent.disk_free_mb,
            interactive_session=agent.interactive_session,
            pools=agent.pools,
            alerts=agent.alerts,
            max_concurrency=max(1, pools_total or self._legacy_worker_max(agent.worker_id)),
            last_heartbeat_at=agent.last_seen_at,
            is_active=agent.enabled and agent.administrative_status != "disabled",
            active_jobs=active_jobs,
        )

    def _legacy_worker_max(self, worker_id: int | None) -> int:
        if worker_id is None:
            return 1
        worker = self.workers.get(worker_id)
        return worker.max_concurrency if worker else 1

    def _actor(self, user) -> object:
        from modules.fleet.application.dto import ActorDTO

        return ActorDTO(actor_type="user", actor_id=str(user.id))


def _compat_connectivity(status: str | None) -> str:
    if status in {"online", "stale", "disconnected", "offline"}:
        return status
    if status == "busy":
        return "online"
    if status == "disabled":
        return "offline"
    return "offline"
