from sqlalchemy.orm import Session

from app.models.worker import Worker
from app.repositories.worker_repository import WorkerRepository
from app.repositories.job_repository import JobRepository
from app.schemas.worker import WorkerCreate, WorkerRead, WorkerUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class WorkerService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.workers = WorkerRepository(db)
        self.jobs = JobRepository(db)
        self.permissions = PermissionService(db)

    def list_workers(self) -> list[WorkerRead]:
        """List all workers with active job counts."""
        workers = self.workers.list_all()
        worker_data = []
        
        for worker in workers:
            active_jobs = self.jobs.count_running_by_worker(worker.id)
            worker_dict = {
                "id": worker.id,
                "name": worker.name,
                "hostname": worker.hostname,
                "ip_address": worker.ip_address,
                "agent_id": worker.agent_id,
                "machine_id": worker.machine_id,
                "agent_version": worker.agent_version,
                "os": worker.os,
                "architecture": worker.architecture,
                "capabilities_json": worker.capabilities_json,
                "last_payload_json": worker.last_payload_json,
                "status": worker.status,
                "max_concurrency": worker.max_concurrency,
                "last_heartbeat_at": worker.last_heartbeat_at,
                "is_active": worker.is_active,
                "active_jobs": active_jobs,
            }
            worker_data.append(WorkerRead(**worker_dict))
        
        return worker_data

    def get_worker(self, worker_id: int) -> WorkerRead:
        """Get a worker with active job count."""
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        
        active_jobs = self.jobs.count_running_by_worker(worker.id)
        worker_dict = {
            "id": worker.id,
            "name": worker.name,
            "hostname": worker.hostname,
            "ip_address": worker.ip_address,
            "agent_id": worker.agent_id,
            "machine_id": worker.machine_id,
            "agent_version": worker.agent_version,
            "os": worker.os,
            "architecture": worker.architecture,
            "capabilities_json": worker.capabilities_json,
            "last_payload_json": worker.last_payload_json,
            "status": worker.status,
            "max_concurrency": worker.max_concurrency,
            "last_heartbeat_at": worker.last_heartbeat_at,
            "is_active": worker.is_active,
            "active_jobs": active_jobs,
        }
        
        return WorkerRead(**worker_dict)

    def get_worker_model(self, worker_id: int) -> Worker:
        """Get the raw worker model."""
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        return worker

    def create_worker(self, user, payload: WorkerCreate) -> WorkerRead:
        self.permissions.ensure_admin_or_manager(user)
        worker = self.workers.create(Worker(**payload.model_dump()))
        self.audit.record(
            "worker_created",
            actor_email=user.email,
            resource_type="worker",
            resource_id=str(worker.id),
            details=worker.name,
        )
        self.db.commit()
        return self.get_worker(worker.id)

    def update_worker(self, user, worker_id: int, payload: WorkerUpdate) -> WorkerRead:
        self.permissions.ensure_admin_or_manager(user)
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        for field, value in payload.model_dump().items():
            setattr(worker, field, value)
        updated = self.workers.update(worker)
        self.audit.record(
            "worker_updated",
            actor_email=user.email,
            resource_type="worker",
            resource_id=str(updated.id),
            details=updated.name,
        )
        self.db.commit()
        return self.get_worker(updated.id)

    def delete_worker(self, user, worker_id: int) -> None:
        self.permissions.ensure_admin_or_manager(user)
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        self.audit.record(
            "worker_deleted",
            actor_email=user.email,
            resource_type="worker",
            resource_id=str(worker.id),
            details=worker.name,
        )
        if worker.jobs or worker.executions or worker.automation_preferences:
            worker.is_active = False
            worker.status = "offline"
            self.workers.update(worker)
            self.db.commit()
            return
        self.workers.delete(worker)
