"""Montagem da fila com as dependências reais (casos de uso de Orchestration e Telemetry)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.dispatch.application.use_cases.queue import DespacharFila, MontarFila, VerFila
from modules.dispatch.infrastructure.repositories import SqlAlchemyResourceLockRepository
from modules.dispatch.infrastructure.repositories.sqlalchemy_queue_view import SqlAlchemyQueueReader
from modules.orchestration.application.use_cases.direct import StartDirectAttempt
from modules.orchestration.application.use_cases.queue import (
    DecidirJobPerdido,
    EnfileirarExecucao,
    MarcarTentativasDiretasPerdidas,
)
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.orchestration.infrastructure.repositories.sqlalchemy_queue import SqlAlchemyQueueStore
from modules.telemetry.application.use_cases.estimates import QueueEstimates
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters


@dataclass(frozen=True)
class Fila:
    ver: VerFila
    despachar: DespacharFila
    enfileirar: EnfileirarExecucao
    decidir_perdido: DecidirJobPerdido
    marcar_perdidos: MarcarTentativasDiretasPerdidas
    reader: SqlAlchemyQueueReader
    store: SqlAlchemyQueueStore
    tasks: object
    transaction: object


def build_fila(db: Session) -> Fila:
    orch = build_orchestration_adapters(db)
    telemetry = build_telemetry_adapters(db)
    reader = SqlAlchemyQueueReader(db)
    store = SqlAlchemyQueueStore(db)
    locks = SqlAlchemyResourceLockRepository(db)

    def tentativa_mais_recente(job_id: str) -> str | None:
        tentativa = store.last_attempt(job_id)
        return tentativa.id if tentativa is not None else None

    estimativas = QueueEstimates(telemetry.steps, telemetry.manifests, telemetry.items.plans, tentativa_mais_recente)
    montar = MontarFila(reader, estimativas.estimar_job, estimativas.restante, estimativas.nomes_das_etapas)
    iniciar = StartDirectAttempt(orch.tasks, orch.attempts)

    def iniciar_direta(**kwargs) -> object:
        return iniciar.execute(package_id=None, **kwargs)

    return Fila(
        ver=VerFila(montar),
        despachar=DespacharFila(montar, reader, orch.tasks, iniciar_direta, orch.transaction),
        enfileirar=EnfileirarExecucao(orch.executions, orch.automation_versions, store),
        decidir_perdido=DecidirJobPerdido(orch.tasks, store, locks),
        marcar_perdidos=MarcarTentativasDiretasPerdidas(reader.tentativas_diretas_sem_sinal, orch.tasks, orch.attempts, locks),
        reader=reader,
        store=store,
        tasks=orch.tasks,
        transaction=orch.transaction,
    )
