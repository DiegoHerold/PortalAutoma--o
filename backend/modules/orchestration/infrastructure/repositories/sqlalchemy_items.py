from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.orchestration.application.use_cases.items import NO_ITEM, StepPlan
from modules.orchestration.infrastructure.orm.models import ExecutionItemRecord, StepPlanRecord


class SqlAlchemyExecutionItemStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_started(self, *, item_id: str, execution_id: str, task_execution_id: str, automation_id: int,
                       item_key: str, label: str | None, group_key: str | None, configuration: dict[str, Any],
                       work_signature: str, at: datetime) -> None:
        stmt = insert(ExecutionItemRecord).values(
            id=item_id, execution_id=execution_id, task_execution_id=task_execution_id, automation_id=automation_id,
            item_key=item_key, label=label, group_key=group_key, configuration=configuration,
            work_signature=work_signature, status="executando", started_at=at, completed_at=None,
        )
        # Item já cadastrado no job (fila, Fase 3) ou retomado: passa a executar de novo.
        stmt = stmt.on_conflict_do_update(
            index_elements=["task_execution_id", "item_key"],
            set_={
                "label": stmt.excluded.label,
                "group_key": stmt.excluded.group_key,
                "configuration": stmt.excluded.configuration,
                "work_signature": stmt.excluded.work_signature,
                "status": "executando",
                "started_at": stmt.excluded.started_at,
                "completed_at": None,
            },
        )
        self.db.execute(stmt)

    def set_finished(self, *, task_execution_id: str, item_key: str, status: str, summary: str | None, at: datetime) -> None:
        self.db.execute(
            update(ExecutionItemRecord)
            .where(ExecutionItemRecord.task_execution_id == task_execution_id, ExecutionItemRecord.item_key == item_key)
            .values(status=status, summary=summary, completed_at=at)
        )

    def set_attention(self, *, task_execution_id: str, item_key: str, attention: dict[str, Any]) -> None:
        self.db.execute(
            update(ExecutionItemRecord)
            .where(ExecutionItemRecord.task_execution_id == task_execution_id, ExecutionItemRecord.item_key == item_key)
            .values(attention=attention)
        )

    def work_signature(self, task_execution_id: str, item_key: str) -> str | None:
        return self.db.scalar(
            select(ExecutionItemRecord.work_signature)
            .where(ExecutionItemRecord.task_execution_id == task_execution_id, ExecutionItemRecord.item_key == item_key)
        )

    def item_keys(self, task_execution_id: str) -> list[str]:
        return list(self.db.scalars(
            select(ExecutionItemRecord.item_key).where(ExecutionItemRecord.task_execution_id == task_execution_id)
            .order_by(ExecutionItemRecord.item_key)
        ))

    def plan_step(self, *, task_execution_id: str, item_key: str, step_key: str, planned_tasks: int | None) -> None:
        stmt = insert(StepPlanRecord).values(task_execution_id=task_execution_id, item_key=item_key, step_key=step_key,
                                             planned_tasks=planned_tasks, completed_tasks=0)
        if planned_tasks is None:
            stmt = stmt.on_conflict_do_nothing(index_elements=["task_execution_id", "item_key", "step_key"])
        else:
            stmt = stmt.on_conflict_do_update(index_elements=["task_execution_id", "item_key", "step_key"],
                                              set_={"planned_tasks": planned_tasks})
        self.db.execute(stmt)

    def add_completed_tasks(self, *, task_execution_id: str, item_key: str, step_key: str, tasks: int) -> None:
        stmt = insert(StepPlanRecord).values(task_execution_id=task_execution_id, item_key=item_key, step_key=step_key,
                                             planned_tasks=None, completed_tasks=tasks)
        stmt = stmt.on_conflict_do_update(
            index_elements=["task_execution_id", "item_key", "step_key"],
            set_={"completed_tasks": StepPlanRecord.completed_tasks + tasks},
        )
        self.db.execute(stmt)

    def plans(self, task_execution_id: str) -> list[StepPlan]:
        rows = self.db.scalars(select(StepPlanRecord).where(StepPlanRecord.task_execution_id == task_execution_id))
        return [StepPlan(None if r.item_key == NO_ITEM else r.item_key, r.step_key, r.planned_tasks, r.completed_tasks)
                for r in rows]
