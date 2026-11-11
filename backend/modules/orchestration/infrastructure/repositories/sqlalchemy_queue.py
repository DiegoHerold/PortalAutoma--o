from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.orchestration.application.dto import TaskExecutionDTO
from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    ExecutionItemRecord,
    StepPlanRecord,
    TaskExecutionRecord,
)

ATIVOS = "dedup_key IS NOT NULL AND status IN ('queued', 'ready', 'running')"


class SqlAlchemyQueueStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_job_or_existing(self, task: TaskExecutionDTO) -> tuple[str, bool]:
        """Insere o job; se o mesmo pedido já está na fila ou rodando, devolve o existente.
        O índice único parcial resolve até dois pedidos chegando ao mesmo tempo."""
        criado = self.db.execute(
            insert(TaskExecutionRecord).values(**task.__dict__)
            .on_conflict_do_nothing(index_elements=["dedup_key"], index_where=text(ATIVOS))
            .returning(TaskExecutionRecord.id)
        ).scalar_one_or_none()
        if criado is not None:
            return criado, True
        existente = self.db.scalar(select(TaskExecutionRecord.id).where(
            TaskExecutionRecord.dedup_key == task.dedup_key,
            TaskExecutionRecord.status.in_(["queued", "ready", "running"])))
        return existente, False

    def create_pending_items(self, *, execution_id: str, task_execution_id: str, automation_id: int,
                             itens: list[dict[str, Any]]) -> None:
        from uuid import uuid4

        self.db.execute(insert(ExecutionItemRecord).values([
            {"id": f"itm_{uuid4().hex}", "execution_id": execution_id, "task_execution_id": task_execution_id,
             "automation_id": automation_id, "item_key": str(i["chave"]), "label": i.get("rotulo"),
             "group_key": str(i.get("grupo") or i["chave"]), "configuration": i.get("configuracao") or {},
             "work_signature": i["assinatura"], "status": "pendente"}
            for i in itens
        ]).on_conflict_do_nothing(index_elements=["task_execution_id", "item_key"]))

    def reset_progress(self, task_execution_id: str) -> None:
        """Recomeçar do zero: tarefas feitas zeram e os itens voltam a pendente."""
        self.db.execute(delete(StepPlanRecord).where(StepPlanRecord.task_execution_id == task_execution_id))
        self.db.execute(update(ExecutionItemRecord).where(ExecutionItemRecord.task_execution_id == task_execution_id)
                        .values(status="pendente", summary=None, attention=None, started_at=None, completed_at=None))

    def last_attempt(self, task_execution_id: str) -> Any:
        return self.db.scalar(select(ExecutionAttemptRecord)
                              .where(ExecutionAttemptRecord.task_execution_id == task_execution_id)
                              .order_by(ExecutionAttemptRecord.attempt_number.desc()).limit(1))
