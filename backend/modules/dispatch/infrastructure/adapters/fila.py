"""Montagem da fila com as dependências reais (casos de uso de Orchestration e Telemetry)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.dispatch.application.use_cases.queue import DespacharFila, MontarFila, VerFila
from modules.dispatch.infrastructure.repositories import SqlAlchemyResourceLockRepository
from modules.dispatch.infrastructure.repositories.sqlalchemy_queue_view import SqlAlchemyQueueReader
from modules.orchestration.application.use_cases.direct import StartDirectAttempt
from modules.orchestration.application.use_cases.queue import (
    ContinuarExecucao,
    DecidirJobPerdido,
    EncerrarTentativaDireta,
    EnfileirarExecucao,
    MarcarTentativasDiretasPerdidas,
    PararExecucao,
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
    iniciar = StartDirectAttempt(orch.tasks, orch.attempts, orch.executions)

    def iniciar_direta(**kwargs) -> object:
        return iniciar.execute(package_id=None, **kwargs)

    return Fila(
        ver=VerFila(montar),
        despachar=DespacharFila(montar, reader, orch.tasks, iniciar_direta, orch.transaction),
        enfileirar=EnfileirarExecucao(orch.executions, orch.automation_versions, store),
        decidir_perdido=DecidirJobPerdido(orch.tasks, store, locks),
        marcar_perdidos=MarcarTentativasDiretasPerdidas(reader.tentativas_diretas_sem_sinal, build_encerrar(db)),
        reader=reader,
        store=store,
        tasks=orch.tasks,
        transaction=orch.transaction,
    )


def build_encerrar(db: Session) -> EncerrarTentativaDireta:
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectDeliveryReader

    orch = build_orchestration_adapters(db)
    return EncerrarTentativaDireta(orch.executions, orch.tasks, orch.attempts, SqlAlchemyResourceLockRepository(db),
                                   SqlAlchemyDirectDeliveryReader(db).revogar_tokens)


def build_parar(db: Session, cancelar_no_agent: Callable[[str, str | None], object]) -> PararExecucao:
    """``cancelar_no_agent``: o cancelamento que já existia para o modo agente (faz o próprio commit)."""
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore

    orch = build_orchestration_adapters(db)
    return PararExecucao(orch.executions, orch.tasks, SqlAlchemyQueueStore(db), SqlAlchemyDirectCommandStore(db),
                         SqlAlchemyResourceLockRepository(db), cancelar_no_agent)


def build_continuar(db: Session) -> ContinuarExecucao:
    orch = build_orchestration_adapters(db)
    passos = build_telemetry_adapters(db).steps

    def etapas_concluidas(execution_id: str) -> dict[str, list[str]]:
        """Etapas que terminaram ok em cada item (lidas da Telemetry, só leitura)."""
        saida: dict[str, list[str]] = {}
        for run in passos.for_execution(execution_id):
            if run.status == "ok" and run.item_key and run.step_key not in saida.get(run.item_key, []):
                saida.setdefault(run.item_key, []).append(run.step_key)
        return saida

    store = SqlAlchemyQueueStore(db)
    return ContinuarExecucao(orch.executions, orch.tasks, store,
                             EnfileirarExecucao(orch.executions, orch.automation_versions, store), etapas_concluidas)
