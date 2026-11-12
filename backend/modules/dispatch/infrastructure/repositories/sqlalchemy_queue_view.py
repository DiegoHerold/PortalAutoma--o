"""Leitura do estado da fila e das máquinas, e a trava de tela do modo direto.

Só leitura das tabelas de outros contextos (Orchestration, Fleet, Telemetry, Catalog);
escrita só na trava (``resource_locks``, que é do Dispatch).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.dispatch.domain.resource_lock import normalize_resource_key
from modules.dispatch.infrastructure.orm.models import ResourceLockRecord
from modules.fleet.infrastructure.orm.models import (
    AgentRecord,
    DirectInstanceRecord,
    InteractiveSessionSnapshotRecord,
    MachineRecord,
)
from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    ExecutionItemRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
)

ATIVAS = ("offered", "accepted", "committed", "preparing", "running", "cancel_requested")
from modules.dispatch.domain.comunicacao import SEM_COMUNICACAO

SINAL_DIRETO = SEM_COMUNICACAO  # sem sinal por isso, a execução direta é cancelada
ESCOPO_TELA = "maquina_tela"


def chave_tela(machine_id: str) -> str:
    return f"machine:{machine_id}:screen"


@dataclass
class MaquinaLida:
    id: str
    nome: str
    capacidade: dict[str, int]
    agentes: list[dict[str, Any]] = field(default_factory=list)       # online, habilitado, sessão bloqueada
    diretas: list[dict[str, Any]] = field(default_factory=list)       # automation_id, status, com sinal
    rodando: list[dict[str, Any]] = field(default_factory=list)       # job_id, pool, tentativa, desde
    perdido: bool = False


class SqlAlchemyQueueReader:
    def __init__(self, db: Session) -> None:
        self.db = db

    def jobs_na_fila(self) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(TaskExecutionRecord, OrchestrationExecutionRecord.created_at)
            .join(OrchestrationExecutionRecord, OrchestrationExecutionRecord.id == TaskExecutionRecord.execution_id)
            .where(TaskExecutionRecord.status == "queued", TaskExecutionRecord.enqueue_batch_id.is_not(None))
        ).all()
        saida = []
        for tarefa, criada in linhas:
            itens = self.db.execute(
                select(ExecutionItemRecord.item_key, ExecutionItemRecord.label, ExecutionItemRecord.work_signature)
                .where(ExecutionItemRecord.task_execution_id == tarefa.id).order_by(ExecutionItemRecord.item_key)
            ).all()
            saida.append({"tarefa": tarefa, "lote_criado": criada,
                          "itens": [{"chave": k, "rotulo": r, "assinatura": a} for k, r, a in itens]})
        return saida

    def maquinas(self, agora: datetime) -> list[MaquinaLida]:
        maquinas = {m.id: MaquinaLida(m.id, m.name, dict(m.pool_capacity or {}))
                    for m in self.db.scalars(select(MachineRecord).where(MachineRecord.status == "ativa"))}
        for agente in self.db.scalars(select(AgentRecord).where(AgentRecord.machine_id.is_not(None))):
            if agente.machine_id not in maquinas:
                continue
            sessao = self.db.scalar(select(InteractiveSessionSnapshotRecord.locked)
                                    .where(InteractiveSessionSnapshotRecord.agent_id == agente.id)
                                    .order_by(InteractiveSessionSnapshotRecord.observed_at.desc()).limit(1))
            maquinas[agente.machine_id].agentes.append({
                "id": agente.id, "online": agente.connectivity_status == "online",
                "habilitado": bool(agente.enabled) and agente.administrative_status in ("enabled", "active"),
                "bloqueada": bool(sessao)})
        for instancia in self.db.scalars(select(DirectInstanceRecord).where(DirectInstanceRecord.machine_id.is_not(None))):
            if instancia.machine_id not in maquinas:
                continue
            maquinas[instancia.machine_id].diretas.append({
                "id": instancia.id, "automation_id": instancia.automation_id, "status": instancia.status,
                "com_sinal": instancia.last_seen_at is not None and instancia.last_seen_at >= agora - SINAL_DIRETO})
        maquina_da_tentativa = func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id)
        ativos = self.db.execute(
            select(ExecutionAttemptRecord, TaskExecutionRecord, maquina_da_tentativa)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .where(ExecutionAttemptRecord.status.in_(ATIVAS))
        ).all()
        for tentativa, tarefa, maquina_id in ativos:
            if maquina_id in maquinas:
                maquinas[maquina_id].rodando.append({
                    "job_id": tarefa.id, "execution_id": tarefa.execution_id, "tentativa_id": tentativa.id,
                    "pool": tarefa.pool or (tarefa.requirements_snapshot or {}).get("execution_mode") or "background",
                    "desde": tentativa.started_at or tentativa.committed_at or tentativa.created_at})
        perdidos = self.db.execute(
            select(func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id))
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .where(TaskExecutionRecord.status == "lost",
                   ExecutionAttemptRecord.attempt_number == TaskExecutionRecord.current_attempt_number)
        ).scalars().all()
        for maquina_id in perdidos:
            if maquina_id in maquinas:
                maquinas[maquina_id].perdido = True
        return list(maquinas.values())

    def automation_name(self, automation_id: int | None) -> str | None:
        from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

        if not automation_id:
            return None
        return self.db.scalar(select(CatalogAutomationRecord.name).where(CatalogAutomationRecord.id == automation_id))

    def jobs_perdidos(self) -> list[dict[str, Any]]:
        maquina = func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id)
        linhas = self.db.execute(
            select(TaskExecutionRecord, maquina, MachineRecord.name)
            .join(ExecutionAttemptRecord, (ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id)
                  & (ExecutionAttemptRecord.attempt_number == TaskExecutionRecord.current_attempt_number))
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .outerjoin(MachineRecord, MachineRecord.id == maquina)
            .where(TaskExecutionRecord.status == "lost")
        ).all()
        return [{"tarefa": t, "maquina_id": m, "maquina_nome": n} for t, m, n in linhas]

    def descrever_job(self, job_id: str) -> tuple[int | None, list[str]]:
        """Automação e itens de um job (para nomear quem segura a fila)."""
        tarefa = self.db.get(TaskExecutionRecord, job_id)
        if tarefa is None:
            return None, []
        itens = self.db.scalars(select(ExecutionItemRecord.item_key)
                                .where(ExecutionItemRecord.task_execution_id == job_id)
                                .order_by(ExecutionItemRecord.item_key)).all()
        return self.automation_id(tarefa.automation_version_id), list(itens)

    def automation_id(self, automation_version_id: int) -> int | None:
        from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord

        return self.db.scalar(select(CatalogAutomationVersionRecord.automation_id)
                              .where(CatalogAutomationVersionRecord.id == automation_version_id))

    def savepoint(self) -> Any:
        return self.db.begin_nested()

    def tentar_trava_de_tela(self, *, lock_id: str, machine_id: str, attempt_id: str, agora: datetime,
                             validade: timedelta) -> bool:
        """Uma trava de tela por máquina, nos dois modos. O índice único resolve a corrida."""
        chave = chave_tela(machine_id)
        criada = self.db.execute(insert(ResourceLockRecord).values(
            id=lock_id, resource_key=chave, normalized_key=normalize_resource_key(chave), scope=ESCOPO_TELA,
            agent_id=None, machine_id=machine_id, execution_attempt_id=attempt_id, status="active",
            acquired_at=agora, expires_at=agora + validade,
        ).on_conflict_do_nothing().returning(ResourceLockRecord.id)).scalar_one_or_none()
        return criada is not None

    def tela_ocupada(self, machine_id: str) -> bool:
        chave = normalize_resource_key(chave_tela(machine_id))
        return self.db.scalar(select(func.count(ResourceLockRecord.id)).where(
            ResourceLockRecord.scope == ESCOPO_TELA, ResourceLockRecord.normalized_key == chave,
            ResourceLockRecord.status == "active")) > 0

    def ready_sem_tentativa(self) -> list[Any]:
        """Jobs da fila liberados para um Agent que não chegou a aceitar (recusou ou saiu)."""
        ativa = (select(ExecutionAttemptRecord.id)
                 .where(ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id,
                        ExecutionAttemptRecord.status.in_(ATIVAS)).exists())
        return list(self.db.scalars(select(TaskExecutionRecord).where(
            TaskExecutionRecord.status == "ready", TaskExecutionRecord.enqueue_batch_id.is_not(None),
            TaskExecutionRecord.last_scheduling_failure.is_not(None), ~ativa)))

    def tentativas_diretas_sem_sinal(self, agora: datetime) -> list[tuple[str, str]]:
        """(tentativa, job) do modo direto rodando numa instância que parou de dar sinal."""
        limite = agora - SINAL_DIRETO
        return [(a, t) for a, t in self.db.execute(
            select(ExecutionAttemptRecord.id, ExecutionAttemptRecord.task_execution_id)
            .join(DirectInstanceRecord, DirectInstanceRecord.id == ExecutionAttemptRecord.executor_id)
            .where(ExecutionAttemptRecord.executor_type == "direct", ExecutionAttemptRecord.status.in_(ATIVAS),
                   or_(DirectInstanceRecord.last_seen_at.is_(None), DirectInstanceRecord.last_seen_at < limite),
                   ExecutionAttemptRecord.created_at < limite)
        ).all()]
