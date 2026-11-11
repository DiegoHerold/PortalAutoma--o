"""O que a Orquestração tem numa máquina: o que está rodando e o que espera na fila só por ela.

Usado pelo Fleet ao apagar uma máquina. Só a Orquestração mexe nos jobs: ``liberar`` tira a
máquina obrigatória dos jobs que ainda não começaram (eles voltam a poder ir para qualquer
máquina que sirva).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord, TaskExecutionRecord

# Tentativas que ocupam a máquina (as mesmas que o despacho conta, sqlalchemy_queue_view.ATIVAS).
ATIVAS = ("offered", "accepted", "committed", "preparing", "running", "cancel_requested")
ESPERANDO = ("pending", "ready", "queued")


class SqlAlchemyUsoDaMaquina:
    def __init__(self, db: Session) -> None:
        self.db = db

    def rodando(self, machine_id: str) -> int:
        """Tentativas ativas na máquina, pela máquina da tentativa ou pela do Agent dela."""
        from modules.fleet.infrastructure.orm.models import AgentRecord

        maquina = func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id)
        return int(self.db.scalar(
            select(func.count()).select_from(ExecutionAttemptRecord)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .where(maquina == machine_id, ExecutionAttemptRecord.status.in_(ATIVAS))) or 0)

    def na_fila_exigindo(self, machine_id: str) -> int:
        return int(self.db.scalar(select(func.count()).select_from(TaskExecutionRecord).where(
            TaskExecutionRecord.required_machine_id == machine_id, TaskExecutionRecord.status.in_(ESPERANDO))) or 0)

    def liberar(self, machine_id: str) -> int:
        resultado: Any = self.db.execute(update(TaskExecutionRecord).where(
            TaskExecutionRecord.required_machine_id == machine_id, TaskExecutionRecord.status.in_(ESPERANDO),
        ).values(required_machine_id=None))
        self.db.flush()
        return int(resultado.rowcount or 0)
