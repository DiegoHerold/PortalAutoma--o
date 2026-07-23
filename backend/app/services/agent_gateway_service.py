from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import JobPriority, JobStatus, WorkerStatus
from app.models.automation import Automation
from app.models.execution import Execution
from app.models.job import Job
from app.models.log import ExecutionLog
from app.models.worker import Worker
from app.services.realtime_service import RealtimeService
from app.utils.datetime import utcnow


@dataclass(frozen=True)
class AgentCommand:
    job_id: int
    execution_id: int
    payload: dict[str, Any]


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


class AgentGatewayService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register_agent(self, payload: dict[str, Any], bearer_token: str | None = None) -> dict[str, Any]:
        worker = self._find_worker_for_registration(payload, bearer_token)
        now = utcnow()
        if worker is None:
            worker = Worker(
                name=payload.get("hostname") or "Automation Agent",
                hostname=payload.get("hostname") or "unknown",
                status=WorkerStatus.ONLINE,
                max_concurrency=1,
                is_active=True,
            )
            self.db.add(worker)
            self.db.flush()

        worker.hostname = payload.get("hostname") or worker.hostname
        worker.name = worker.name or worker.hostname
        worker.machine_id = payload.get("machine_id") or worker.machine_id
        worker.os = payload.get("os") or worker.os
        worker.architecture = payload.get("architecture") or worker.architecture
        worker.agent_version = payload.get("agent_version") or worker.agent_version
        worker.capabilities_json = payload.get("capabilities") or []
        worker.last_payload_json = payload
        worker.status = WorkerStatus.ONLINE if worker.is_active else WorkerStatus.DISABLED
        worker.last_heartbeat_at = now

        if not worker.agent_id:
            worker.agent_id = f"agent_{worker.id}"
        if not worker.device_token:
            worker.device_token = secrets.token_urlsafe(32)

        self.db.commit()
        self.db.refresh(worker)
        return {
            "agent_id": worker.agent_id,
            "worker_id": worker.agent_id,
            "device_token": worker.device_token,
            "heartbeat_seconds": 30,
        }

    def heartbeat(self, agent_id: str, bearer_token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        worker = self.authenticate_agent(agent_id, bearer_token)
        current_execution_ids = payload.get("current_execution_ids") or []
        available_slots = payload.get("available_slots")
        if isinstance(available_slots, int):
            worker.max_concurrency = max(1, available_slots + len(current_execution_ids))
        worker.agent_version = payload.get("agent_version") or worker.agent_version
        worker.last_payload_json = payload
        worker.last_heartbeat_at = utcnow()
        if worker.is_active:
            worker.status = WorkerStatus.BUSY if current_execution_ids else WorkerStatus.ONLINE
        else:
            worker.status = WorkerStatus.DISABLED
        self.db.commit()
        return {"ok": True, "server_time": utcnow().isoformat()}

    def record_events(self, agent_id: str, bearer_token: str | None, events: list[dict[str, Any]]) -> dict[str, Any]:
        worker = self.authenticate_agent(agent_id, bearer_token)
        synced_ids: list[str] = []
        for event in events:
            execution = self._execution_from_external_id(event.get("execution_id"))
            if execution is None:
                continue
            payload = event.get("payload") or {}
            level = "INFO"
            message = payload.get("message") or json.dumps(payload, ensure_ascii=False)
            self.db.add(
                ExecutionLog(
                    execution_id=execution.id,
                    level=level,
                    message=f"[agent:{worker.agent_id}] {event.get('event_type')}: {message}",
                )
            )
            synced_ids.append(str(event.get("event_id")))
        self.db.commit()
        return {"ok": True, "synced_event_ids": synced_ids}

    def authenticate_by_token(self, bearer_token: str | None) -> Worker | None:
        if not bearer_token:
            return None
        return self.db.scalar(select(Worker).where(Worker.device_token == bearer_token))

    def authenticate_agent(self, agent_id: str, bearer_token: str | None) -> Worker:
        worker = self.db.scalar(select(Worker).where(Worker.agent_id == agent_id))
        if worker is None or not worker.device_token or worker.device_token != bearer_token:
            raise ValueError("Agente nao autorizado.")
        return worker

    def claim_next_command(self, worker_id: int) -> AgentCommand | None:
        worker = self.db.get(Worker, worker_id)
        if worker is None or not worker.is_active:
            return None
        if self._running_count(worker.id) >= max(1, worker.max_concurrency):
            return None

        job = self._next_queued_job(worker.id)
        if job is None:
            return None

        automation = self.db.get(Automation, job.automation_id)
        if automation is None or not automation.is_active:
            self._fail_job(job, worker, "Automacao inativa ou inexistente.")
            self.db.commit()
            self._emit_job_update(job)
            return None
        if not automation.package_url:
            self._fail_job(job, worker, "Automation package_url nao configurado.")
            self.db.commit()
            self._emit_job_update(job)
            return None

        now = utcnow()
        job.status = JobStatus.RUNNING
        job.assigned_worker_id = worker.id
        job.started_at = now
        worker.status = WorkerStatus.BUSY
        worker.last_heartbeat_at = now
        execution = Execution(
            job_id=job.id,
            worker_id=worker.id,
            execution_status=JobStatus.RUNNING,
            started_at=now,
            result_summary="Comando enviado ao Automation Agent.",
            result_payload_json={},
        )
        self.db.add(execution)
        self.db.flush()
        command_id = f"cmd_{job.id}_{uuid.uuid4().hex[:10]}"
        external_execution_id = f"exec_{execution.id}"
        command = {
            "command_id": command_id,
            "type": "execution.assign",
            "execution_id": external_execution_id,
            "package_url": automation.package_url,
            "parameters": job.payload_json or {},
        }
        if automation.package_sha256:
            command["package_sha256"] = automation.package_sha256
        execution.result_payload_json = {"command": command}
        self.db.commit()
        self._emit_job_update(job)
        return AgentCommand(job_id=job.id, execution_id=execution.id, payload=command)

    def finish_command(self, worker_id: int, job_id: int, execution_id: int, raw_response: str) -> None:
        worker = self.db.get(Worker, worker_id)
        job = self.db.get(Job, job_id)
        execution = self.db.get(Execution, execution_id)
        if worker is None or job is None or execution is None:
            return

        finished_at = utcnow()
        response = json.loads(raw_response)
        result = response.get("response") or {}
        state = str(result.get("state") or "").lower()
        error = result.get("error")

        if state == "succeeded":
            job_status = JobStatus.SUCCESS
            execution_status = JobStatus.SUCCESS
            summary = "Automation Agent concluiu com sucesso."
        elif state == "cancelled":
            job_status = JobStatus.CANCELLED
            execution_status = JobStatus.CANCELLED
            summary = "Automation Agent cancelou a execucao."
        else:
            job_status = JobStatus.FAILED
            execution_status = JobStatus.FAILED
            summary = error or f"Automation Agent retornou estado {state or 'desconhecido'}."

        job.status = job_status
        job.finished_at = finished_at
        job.error_message = None if job_status == JobStatus.SUCCESS else summary
        execution.execution_status = execution_status
        execution.finished_at = finished_at
        execution.result_summary = summary
        execution.result_payload_json = result
        self.db.add(
            ExecutionLog(
                execution_id=execution.id,
                level="ERROR" if job_status == JobStatus.FAILED else "INFO",
                message=summary,
            )
        )
        worker.status = WorkerStatus.ONLINE if worker.is_active else WorkerStatus.DISABLED
        worker.last_heartbeat_at = finished_at
        self.db.commit()
        self._emit_job_update(job)

    def mark_lost(self, worker_id: int, job_id: int, execution_id: int, message: str) -> None:
        worker = self.db.get(Worker, worker_id)
        job = self.db.get(Job, job_id)
        execution = self.db.get(Execution, execution_id)
        now = utcnow()
        if job is not None:
            job.status = JobStatus.FAILED
            job.finished_at = now
            job.error_message = message
        if execution is not None:
            execution.execution_status = JobStatus.FAILED
            execution.finished_at = now
            execution.result_summary = message
            self.db.add(ExecutionLog(execution_id=execution.id, level="ERROR", message=message))
        if worker is not None:
            worker.status = WorkerStatus.OFFLINE
            worker.last_heartbeat_at = now
        self.db.commit()
        if job is not None:
            self._emit_job_update(job)

    def _find_worker_for_registration(self, payload: dict[str, Any], bearer_token: str | None) -> Worker | None:
        if bearer_token:
            worker = self.authenticate_by_token(bearer_token)
            if worker is not None:
                return worker
        machine_id = payload.get("machine_id")
        if machine_id:
            worker = self.db.scalar(select(Worker).where(Worker.machine_id == machine_id))
            if worker is not None:
                return worker
        hostname = payload.get("hostname")
        if hostname:
            return self.db.scalar(select(Worker).where(Worker.hostname == hostname, Worker.agent_id.is_(None)))
        return None

    def _next_queued_job(self, worker_id: int) -> Job | None:
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3,
        }
        jobs = list(
            self.db.scalars(
                select(Job)
                .where(and_(Job.status == JobStatus.QUEUED, or_(Job.assigned_worker_id == worker_id, Job.assigned_worker_id.is_(None))))
                .order_by(Job.created_at)
            ).all()
        )
        jobs.sort(key=lambda job: (job.assigned_worker_id != worker_id, priority_order.get(job.priority, 99), job.created_at))
        return jobs[0] if jobs else None

    def _running_count(self, worker_id: int) -> int:
        return self.db.scalar(
            select(func.count(Job.id)).where(and_(Job.assigned_worker_id == worker_id, Job.status == JobStatus.RUNNING))
        ) or 0

    def _execution_from_external_id(self, execution_id: Any) -> Execution | None:
        if not isinstance(execution_id, str) or not execution_id.startswith("exec_"):
            return None
        try:
            pk = int(execution_id.removeprefix("exec_"))
        except ValueError:
            return None
        return self.db.get(Execution, pk)

    def _fail_job(self, job: Job, worker: Worker, message: str) -> None:
        now = utcnow()
        job.assigned_worker_id = worker.id
        job.status = JobStatus.FAILED
        job.started_at = job.started_at or now
        job.finished_at = now
        job.error_message = message
        execution = Execution(
            job_id=job.id,
            worker_id=worker.id,
            execution_status=JobStatus.FAILED,
            started_at=now,
            finished_at=now,
            result_summary=message,
            result_payload_json={"error": message},
        )
        self.db.add(execution)

    def _emit_job_update(self, job: Job) -> None:
        try:
            RealtimeService(self.db).emit_job_update(job)
        except Exception:
            pass
