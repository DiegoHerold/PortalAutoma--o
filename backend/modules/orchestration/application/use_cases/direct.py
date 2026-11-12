"""Tentativa do modo direto (ADR-018). O Dispatcher da Fase 3 chama este caso de uso ao
entregar o job para uma instância direta; aqui não há oferta nem commit separado."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from modules.orchestration.application.dto import ExecutionAttemptDTO
from modules.orchestration.domain.execution_attempt import ExecutionAttempt


class StartDirectAttempt:
    def __init__(self, tasks: object, attempts: object, executions: object | None = None) -> None:
        self.tasks = tasks
        self.attempts = attempts
        self.executions = executions

    def execute(self, *, task_execution_id: str, direct_instance_id: str, machine_id: str,
                package_id: str | None, now: datetime, attempt_id: str | None = None) -> ExecutionAttemptDTO:
        task = self.tasks.get(task_execution_id)
        if task is None:
            raise LookupError(f"Job {task_execution_id} não encontrado.")
        numero = int(task.current_attempt_number or 0) + 1
        tentativa = ExecutionAttempt.create_direct(
            id=attempt_id or f"att_{uuid4().hex}", task_execution_id=task_execution_id, attempt_number=numero,
            direct_instance_id=direct_instance_id, machine_id=machine_id, package_id=package_id, now=now,
        )
        dto = ExecutionAttemptDTO(**{campo: getattr(tentativa, campo) for campo in ExecutionAttemptDTO.__dataclass_fields__
                                     if hasattr(tentativa, campo)} | {"status": tentativa.status.value})
        salvo = self.attempts.add(dto)
        self.tasks.save(replace(task, status="running", current_attempt_number=numero, started_at=task.started_at or now))
        if self.executions is not None:
            # A execução da fila sai de "queued" quando o primeiro job começa.
            execucao = self.executions.get(task.execution_id)
            if execucao is not None and execucao.status in ("queued", "pending", "created"):
                self.executions.save(replace(execucao, status="running", started_at=execucao.started_at or now))
        return salvo
