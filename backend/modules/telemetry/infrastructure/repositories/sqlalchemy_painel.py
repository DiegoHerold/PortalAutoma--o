"""Leituras do Painel, da linha do tempo e do Histórico (Fase 5). Só leitura."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.fleet.infrastructure.orm.models import AgentRecord, MachineRecord
from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    ExecutionItemRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
)
from modules.telemetry.infrastructure.orm.models import EstimateSnapshotRecord

FINAIS = ("succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "lost")


def _automacoes(db: Session, versoes: set[int]) -> dict[int, tuple[int, str]]:
    from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord, CatalogAutomationVersionRecord

    if not versoes:
        return {}
    linhas = db.execute(
        select(CatalogAutomationVersionRecord.id, CatalogAutomationRecord.id, CatalogAutomationRecord.name)
        .join(CatalogAutomationRecord, CatalogAutomationRecord.id == CatalogAutomationVersionRecord.automation_id)
        .where(CatalogAutomationVersionRecord.id.in_(versoes))
    ).all()
    return {v: (a, n) for v, a, n in linhas}


class SqlAlchemyPainelReader:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _itens(self, tarefas: list[str]) -> dict[str, list[dict[str, str | None]]]:
        if not tarefas:
            return {}
        saida: dict[str, list[dict[str, str | None]]] = {}
        for tarefa, chave, rotulo in self.db.execute(
            select(ExecutionItemRecord.task_execution_id, ExecutionItemRecord.item_key, ExecutionItemRecord.label)
            .where(ExecutionItemRecord.task_execution_id.in_(tarefas)).order_by(ExecutionItemRecord.item_key)
        ):
            saida.setdefault(tarefa, []).append({"chave": chave, "rotulo": rotulo})
        return saida

    def maquinas(self) -> list[tuple[str, str]]:
        return [(m.id, m.name) for m in self.db.scalars(
            select(MachineRecord).where(MachineRecord.status == "ativa").order_by(MachineRecord.name))]

    def rodando(self) -> list[dict[str, Any]]:
        """Jobs rodando agora, com a tentativa atual e a máquina."""
        maquina = func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id)
        linhas = self.db.execute(
            select(TaskExecutionRecord, ExecutionAttemptRecord, maquina, MachineRecord.name, OrchestrationExecutionRecord.created_at)
            .join(ExecutionAttemptRecord, (ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id)
                  & (ExecutionAttemptRecord.attempt_number == TaskExecutionRecord.current_attempt_number))
            .join(OrchestrationExecutionRecord, OrchestrationExecutionRecord.id == TaskExecutionRecord.execution_id)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .outerjoin(MachineRecord, MachineRecord.id == maquina)
            .where(TaskExecutionRecord.status == "running")
            .order_by(ExecutionAttemptRecord.created_at)
        ).all()
        nomes = _automacoes(self.db, {t.automation_version_id for t, *_ in linhas})
        itens = self._itens([t.id for t, *_ in linhas])
        return [{
            "execucao_id": t.execution_id, "job_id": t.id, "tentativa_id": a.id, "tentativa": a.attempt_number,
            "automation_id": nomes.get(t.automation_version_id, (None, None))[0],
            "automacao": nomes.get(t.automation_version_id, (None, None))[1], "pool": t.pool,
            "modo": a.executor_type, "maquina_id": m, "maquina_nome": nome, "itens": itens.get(t.id, []),
            "desde": a.started_at or a.committed_at or a.created_at, "pedida_em": criada,
        } for t, a, m, nome, criada in linhas]

    def tentativas_desde(self, inicio: datetime) -> list[dict[str, Any]]:
        """Tentativas com máquina que tocam a janela: terminaram depois de ``inicio`` ou seguem ativas."""
        maquina = func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id)
        comeco = func.coalesce(ExecutionAttemptRecord.started_at, ExecutionAttemptRecord.committed_at,
                               ExecutionAttemptRecord.created_at)
        linhas = self.db.execute(
            select(ExecutionAttemptRecord, TaskExecutionRecord, maquina, comeco)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .where(maquina.is_not(None),
                   or_(ExecutionAttemptRecord.completed_at.is_(None), ExecutionAttemptRecord.completed_at >= inicio))
            .order_by(comeco)
        ).all()
        nomes = _automacoes(self.db, {t.automation_version_id for _, t, *_ in linhas})
        itens = self._itens([t.id for _, t, *_ in linhas])
        return [{
            "maquina_id": m, "inicio": c, "fim": a.completed_at, "situacao": a.status, "execucao_id": t.execution_id,
            "job_id": t.id, "automation_id": nomes.get(t.automation_version_id, (None, None))[0],
            "automacao": nomes.get(t.automation_version_id, (None, None))[1],
            "itens": [i["chave"] for i in itens.get(t.id, [])], "ativa": a.completed_at is None,
        } for a, t, m, c in linhas]

    def historico(self, *, busca: str | None, automation_id: int | None, situacao: str | None,
                  antes_de: datetime | None, limite: int) -> tuple[list[dict[str, Any]], str | None]:
        """Execuções terminadas, da mais recente. O cursor é o horário da última linha lida
        (não da última devolvida): filtro por texto ou automação nunca trava a paginação."""
        consulta = (select(OrchestrationExecutionRecord)
                    .where(OrchestrationExecutionRecord.status.in_(FINAIS))
                    .order_by(func.coalesce(OrchestrationExecutionRecord.completed_at,
                                            OrchestrationExecutionRecord.created_at).desc())
                    .limit(limite * 3))
        if situacao:
            consulta = consulta.where(OrchestrationExecutionRecord.status == situacao)
        if antes_de is not None:
            consulta = consulta.where(func.coalesce(OrchestrationExecutionRecord.completed_at,
                                                    OrchestrationExecutionRecord.created_at) < antes_de)
        execucoes = list(self.db.scalars(consulta))
        ids = [e.id for e in execucoes]
        if not ids:
            return [], None
        tarefas = list(self.db.scalars(select(TaskExecutionRecord).where(TaskExecutionRecord.execution_id.in_(ids))))
        nomes = _automacoes(self.db, {t.automation_version_id for t in tarefas})
        itens = self._itens([t.id for t in tarefas])
        maquinas = dict(self.db.execute(
            select(TaskExecutionRecord.execution_id, func.string_agg(func.distinct(MachineRecord.name), ", "))
            .join(ExecutionAttemptRecord, ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id)
            .outerjoin(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
            .join(MachineRecord, MachineRecord.id == func.coalesce(ExecutionAttemptRecord.machine_id, AgentRecord.machine_id))
            .where(TaskExecutionRecord.execution_id.in_(ids)).group_by(TaskExecutionRecord.execution_id)
        ).all())
        previstos: dict[str, list[Any]] = {}
        for execucao_id, payload in self.db.execute(
            select(EstimateSnapshotRecord.execution_id, EstimateSnapshotRecord.payload)
            .where(EstimateSnapshotRecord.execution_id.in_(ids))
        ):
            previstos.setdefault(execucao_id, []).append((payload or {}).get("segundos"))
        por_execucao: dict[str, list[Any]] = {}
        for t in tarefas:
            por_execucao.setdefault(t.execution_id, []).append(t)
        saida = []
        termo = (busca or "").strip().lower()
        cursor: str | None = None
        for e in execucoes:
            cursor = (e.completed_at or e.created_at).isoformat()
            suas = por_execucao.get(e.id, [])
            automacao = next((nomes.get(t.automation_version_id) for t in suas if nomes.get(t.automation_version_id)), (None, None))
            if automation_id is not None and automacao[0] != automation_id:
                continue
            chaves = [i for t in suas for i in itens.get(t.id, [])]
            if termo and termo not in (automacao[1] or "").lower() and not any(
                    termo in (i["chave"] or "").lower() or termo in (i["rotulo"] or "").lower() for i in chaves):
                continue
            segundos = previstos.get(e.id)
            previsto = sum(segundos) if segundos and all(s is not None for s in segundos) else None
            inicio, fim = e.started_at or e.created_at, e.completed_at
            saida.append({
                "execucao_id": e.id, "status": e.status, "automation_id": automacao[0], "automacao": automacao[1],
                "itens": [i["chave"] for i in chaves][:8], "total_itens": len(chaves),
                "maquinas": maquinas.get(e.id), "iniciada_em": inicio.isoformat() if inicio else None,
                "concluida_em": fim.isoformat() if fim else None,
                "duracao_s": (fim - inicio).total_seconds() if fim and inicio else None,
                "previsto_s": previsto, "falha": e.failure_summary,
            })
            if len(saida) >= limite:
                break
        terminou = len(saida) < limite and len(execucoes) < limite * 3
        return saida, (None if terminou else cursor)
