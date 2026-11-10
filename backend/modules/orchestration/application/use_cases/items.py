"""Itens da execução e plano de tarefas por etapa.

Orchestration é dono de ``execution_items`` e ``step_plans``. O Telemetry, ao receber os
eventos da automação, pede as gravações por este caso de uso (docs/modules.md: Telemetry
não altera tabela de Orchestration diretamente).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

ITEM_STATUSES = {"pendente", "executando", "ok", "erro", "atencao", "cancelado", "ignorado"}
NO_ITEM = ""  # chave do plano para etapa sem item


@dataclass(frozen=True)
class StepPlan:
    item_key: str | None
    step_key: str
    planned_tasks: int | None
    completed_tasks: int


class ExecutionItemStore(Protocol):
    def upsert_started(self, *, item_id: str, execution_id: str, task_execution_id: str, automation_id: int,
                       item_key: str, label: str | None, group_key: str | None, configuration: dict[str, Any],
                       work_signature: str, at: datetime) -> None: ...

    def set_finished(self, *, task_execution_id: str, item_key: str, status: str, summary: str | None, at: datetime) -> None: ...

    def set_attention(self, *, task_execution_id: str, item_key: str, attention: dict[str, Any]) -> None: ...

    def work_signature(self, task_execution_id: str, item_key: str) -> str | None: ...

    def item_keys(self, task_execution_id: str) -> list[str]: ...

    def plan_step(self, *, task_execution_id: str, item_key: str, step_key: str, planned_tasks: int | None) -> None: ...

    def add_completed_tasks(self, *, task_execution_id: str, item_key: str, step_key: str, tasks: int) -> None: ...

    def plans(self, task_execution_id: str) -> list[StepPlan]: ...


class RecordExecutionItemProgress:
    def __init__(self, store: ExecutionItemStore) -> None:
        self.store = store

    def item_started(self, *, execution_id: str, task_execution_id: str, automation_id: int, item_key: str,
                     label: str | None, group_key: str | None, configuration: dict[str, Any],
                     work_signature: str, at: datetime) -> None:
        self.store.upsert_started(item_id=f"itm_{uuid4().hex}", execution_id=execution_id,
                                  task_execution_id=task_execution_id, automation_id=automation_id,
                                  item_key=item_key, label=label, group_key=group_key,
                                  configuration=configuration, work_signature=work_signature, at=at)

    def item_finished(self, *, task_execution_id: str, item_key: str, status: str, summary: str | None, at: datetime) -> None:
        if status not in ITEM_STATUSES:
            raise ValueError(f"Situação de item inválida: {status}.")
        self.store.set_finished(task_execution_id=task_execution_id, item_key=item_key, status=status, summary=summary, at=at)

    def item_attention(self, *, task_execution_id: str, item_key: str, attention: dict[str, Any]) -> None:
        self.store.set_attention(task_execution_id=task_execution_id, item_key=item_key, attention=attention)

    def work_signature(self, task_execution_id: str, item_key: str | None) -> str | None:
        return self.store.work_signature(task_execution_id, item_key) if item_key else None

    def item_keys(self, task_execution_id: str) -> list[str]:
        return self.store.item_keys(task_execution_id)

    def step_planned(self, *, task_execution_id: str, item_key: str | None, step_key: str, planned_tasks: int | None) -> None:
        """``planned_tasks`` é o total da etapa no job, contando o que outras tentativas já fizeram."""
        self.store.plan_step(task_execution_id=task_execution_id, item_key=item_key or NO_ITEM, step_key=step_key,
                             planned_tasks=planned_tasks)

    def tasks_completed(self, *, task_execution_id: str, item_key: str | None, step_key: str, tasks: int) -> None:
        if tasks > 0:
            self.store.add_completed_tasks(task_execution_id=task_execution_id, item_key=item_key or NO_ITEM,
                                           step_key=step_key, tasks=tasks)

    def plans(self, task_execution_id: str) -> list[StepPlan]:
        return self.store.plans(task_execution_id)
