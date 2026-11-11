"""Imagens dos passos (``step_images``) e a leitura dos eventos para o Acompanhar."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
from modules.telemetry.domain.acompanhamento import EventoDaAutomacao
from modules.telemetry.infrastructure.orm.models import ExecutionEventRecord, StepImageRecord

TIPOS_DE_ESTADO = ("etapa.iniciada", "etapa.concluida", "item.iniciado", "item.concluido", "progresso", "passo",
                   "espera.atualizada", "atencao", "pausa.iniciada", "pausa.concluida", "execucao.iniciada",
                   "execucao.concluida")


class SqlAlchemyStepImageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, attempt_id: str, imagem_id: str) -> StepImageRecord | None:
        return self.db.scalar(select(StepImageRecord).where(StepImageRecord.execution_attempt_id == attempt_id,
                                                            StepImageRecord.imagem_id == imagem_id))

    def da_execucao(self, execution_id: str, imagem_id: str) -> StepImageRecord | None:
        return self.db.scalar(select(StepImageRecord).where(
            StepImageRecord.execution_id == execution_id, StepImageRecord.imagem_id == imagem_id,
            StepImageRecord.status == "pronta").order_by(StepImageRecord.created_at.desc()).limit(1))

    def prontas(self, execution_id: str) -> set[str]:
        return set(self.db.scalars(select(StepImageRecord.imagem_id).where(
            StepImageRecord.execution_id == execution_id, StepImageRecord.status == "pronta")).all())

    def automation_id_da_tarefa(self, task_execution_id: str) -> int | None:
        from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord

        return self.db.scalar(select(CatalogAutomationVersionRecord.automation_id)
                              .join(TaskExecutionRecord,
                                    TaskExecutionRecord.automation_version_id == CatalogAutomationVersionRecord.id)
                              .where(TaskExecutionRecord.id == task_execution_id))

    def adicionar(self, **campos: Any) -> bool:
        """False se a mesma imagem chegou ao mesmo tempo por outra requisição (idempotente)."""
        try:
            with self.db.begin_nested():
                self.db.add(StepImageRecord(**campos))
            return True
        except IntegrityError:
            return False

    def eventos_de_estado(self, execution_id: str, limite: int = 3000) -> list[EventoDaAutomacao]:
        """Os eventos da automação que descrevem o agora (sem os logs), dos mais recentes."""
        tipo = ExecutionEventRecord.payload["type"].astext
        linhas = self.db.execute(
            select(ExecutionEventRecord.id, ExecutionEventRecord.payload, ExecutionEventRecord.occurred_at,
                   ExecutionEventRecord.execution_attempt_id, ExecutionEventRecord.event_sequence)
            .where(ExecutionEventRecord.execution_id == execution_id,
                   ExecutionEventRecord.event_type == "automation.event", tipo.in_(TIPOS_DE_ESTADO))
            .order_by(ExecutionEventRecord.occurred_at.desc(), ExecutionEventRecord.event_sequence.desc()).limit(limite)
        ).all()
        return [EventoDaAutomacao(i, str(p.get("type")), dict(p.get("payload") or {}), quando, tentativa, seq)
                for i, p, quando, tentativa, seq in linhas]

    def logs(self, execution_id: str, *, depois_de: tuple[datetime, int, str] | None, limite: int,
             esconder_espera: bool) -> tuple[list[dict[str, Any]], str | None]:
        """Logs da automação (contrato novo) e logs antigos (stdout/stderr), em ordem de chegada.

        Sem cursor: os ``limite`` mais recentes. Com cursor: os que chegaram depois dele.
        Devolve também o id da linha mais nova lida (log ou não): é o cursor da próxima
        busca, para não reler passos e progresso sem fim quando eles são a maioria."""
        filtro = [ExecutionEventRecord.execution_id == execution_id,
                  ExecutionEventRecord.event_type.in_(["automation.event", "log", "warning", "error"])]
        # Um lote chega com o mesmo received_at; a sequência da automação desempata (o id é aleatório).
        ordem = (ExecutionEventRecord.received_at, ExecutionEventRecord.event_sequence, ExecutionEventRecord.id)
        if depois_de is not None:
            filtro.append(tuple_(*ordem) > tuple_(*depois_de))
            consulta = select(ExecutionEventRecord).where(*filtro).order_by(*ordem)
        else:
            consulta = select(ExecutionEventRecord).where(*filtro).order_by(*(c.desc() for c in ordem))
        saida: list[dict[str, Any]] = []
        cursor: str | None = None
        for linha in self.db.scalars(consulta.limit(limite * 4)):
            if depois_de is not None or cursor is None:
                cursor = linha.id  # avançando: a última lida; do fim para trás: a primeira (mais nova)
            item = _como_log(linha, esconder_espera)
            if item is not None:
                saida.append(item)
            if len(saida) >= limite:
                break
        if depois_de is None:
            saida.reverse()
        return saida, cursor

    def situacoes(self, execution_id: str) -> dict[str, dict[str, Any]]:
        """Situação de cada imagem da execução: pronta, recusada (com o motivo) ou apagada pela retenção."""
        linhas = self.db.execute(select(StepImageRecord.imagem_id, StepImageRecord.status, StepImageRecord.motivo_recusa,
                                        StepImageRecord.apagada_em)
                                 .where(StepImageRecord.execution_id == execution_id)).all()
        return {i: ({"situacao": "apagada", "motivo": f"apagada pela retenção em {apagada:%d/%m/%Y}"} if apagada
                    else {"situacao": s, "motivo": m}) for i, s, m, apagada in linhas}

    def nome_da_maquina(self, machine_id: str | None, agent_id: str | None) -> tuple[str | None, str | None]:
        from modules.fleet.infrastructure.orm.models import AgentRecord, MachineRecord

        if machine_id is None and agent_id is not None:
            machine_id = self.db.scalar(select(AgentRecord.machine_id).where(AgentRecord.id == agent_id))
        if machine_id is None:
            return None, None
        return machine_id, self.db.scalar(select(MachineRecord.name).where(MachineRecord.id == machine_id))

    def ultimo_evento(self, execution_id: str) -> str | None:
        return self.db.scalar(select(ExecutionEventRecord.id).where(ExecutionEventRecord.execution_id == execution_id)
                              .order_by(ExecutionEventRecord.received_at.desc(), ExecutionEventRecord.event_sequence.desc(),
                                        ExecutionEventRecord.id.desc()).limit(1))

    def posicao(self, event_id: str) -> tuple[datetime, int, str] | None:
        linha = self.db.execute(select(ExecutionEventRecord.received_at, ExecutionEventRecord.event_sequence,
                                       ExecutionEventRecord.id)
                                .where(ExecutionEventRecord.id == event_id)).one_or_none()
        return (linha[0], linha[1], linha[2]) if linha else None


def _como_log(linha: ExecutionEventRecord, esconder_espera: bool) -> dict[str, Any] | None:
    if linha.event_type == "automation.event":
        if (linha.payload or {}).get("type") != "log":
            return None
        corpo = (linha.payload or {}).get("payload") or {}
        if esconder_espera and corpo.get("espera"):
            return None
        return {"id": linha.id, "nivel": corpo.get("nivel"), "texto": corpo.get("texto"), "item": corpo.get("item"),
                "espera": bool(corpo.get("espera")), "quando": linha.occurred_at.isoformat()}
    return {"id": linha.id, "nivel": {"warning": "aviso", "error": "erro"}.get((linha.level or "").lower(), "info"),
            "texto": linha.message, "item": None, "espera": False, "quando": linha.occurred_at.isoformat()}
