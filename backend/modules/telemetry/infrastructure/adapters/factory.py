from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.orchestration.application.use_cases.items import RecordExecutionItemProgress
from modules.orchestration.infrastructure.repositories.sqlalchemy_items import SqlAlchemyExecutionItemStore
from modules.telemetry.application.use_cases.estimates import EstimateService
from modules.telemetry.application.use_cases.projection import ProjectAutomationEvents
from modules.telemetry.infrastructure.adapters.payload_validation import (
    DefaultEventPayloadValidator,
    RecursiveSecretMasker,
)
from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, PostgresNotifyPublisher, notificar
from modules.telemetry.infrastructure.repositories import (
    SqlAlchemyEventAcknowledgementRepository,
    SqlAlchemyExecutionAttemptTelemetryReader,
    SqlAlchemyExecutionEventRepository,
    SqlAlchemyExecutionMetricRepository,
    SqlAlchemyTelemetryTransaction,
)
from modules.telemetry.infrastructure.repositories.sqlalchemy_steps import SqlAlchemyManifestReader, SqlAlchemyStepRunStore


@dataclass(frozen=True)
class TelemetryAdapters:
    attempts: SqlAlchemyExecutionAttemptTelemetryReader
    events: SqlAlchemyExecutionEventRepository
    acknowledgements: SqlAlchemyEventAcknowledgementRepository
    metrics: SqlAlchemyExecutionMetricRepository
    validator: DefaultEventPayloadValidator
    masker: RecursiveSecretMasker
    realtime: object
    transaction: SqlAlchemyTelemetryTransaction
    steps: SqlAlchemyStepRunStore
    items: RecordExecutionItemProgress
    manifests: SqlAlchemyManifestReader
    estimates: EstimateService
    projector: ProjectAutomationEvents


def _concluir_direta(db: Session):
    from modules.dispatch.infrastructure.repositories import SqlAlchemyResourceLockRepository
    from modules.orchestration.application.use_cases.queue import ConcluirTentativaDireta
    from modules.orchestration.infrastructure.adapters import build_orchestration_adapters

    orch = build_orchestration_adapters(db)
    return ConcluirTentativaDireta(orch.executions, orch.tasks, orch.attempts, SqlAlchemyResourceLockRepository(db))


def build_registrar_imagem(db: Session):
    """Imagem de passo nos dois modos: confere, gera as medidas e guarda pelo Storage."""
    from modules.storage.application.use_cases.objetos import GuardarObjeto
    from modules.storage.infrastructure.adapters import build_storage_adapters
    from modules.telemetry.application.use_cases.imagens import RegistrarImagemDePasso
    from modules.telemetry.infrastructure.imagens import processar
    from modules.telemetry.infrastructure.repositories.sqlalchemy_images import SqlAlchemyStepImageRepository

    storage = build_storage_adapters(db)
    telemetry = build_telemetry_adapters(db)
    return RegistrarImagemDePasso(
        telemetry.attempts, SqlAlchemyStepImageRepository(db), GuardarObjeto(storage.object_storage, storage.stored_objects),
        processar, telemetry.transaction, lambda execution_id: notificar(CANAL_EXECUCAO, execution_id))


def build_telemetry_adapters(db: Session) -> TelemetryAdapters:
    steps = SqlAlchemyStepRunStore(db)
    # Itens e plano de tarefas são de Orchestration: gravados pelo caso de uso dele.
    items = RecordExecutionItemProgress(SqlAlchemyExecutionItemStore(db))
    manifests = SqlAlchemyManifestReader(db)
    estimates = EstimateService(steps, items, items.plans)
    return TelemetryAdapters(
        attempts=SqlAlchemyExecutionAttemptTelemetryReader(db),
        events=SqlAlchemyExecutionEventRepository(db),
        acknowledgements=SqlAlchemyEventAcknowledgementRepository(db),
        metrics=SqlAlchemyExecutionMetricRepository(db),
        validator=DefaultEventPayloadValidator(),
        masker=RecursiveSecretMasker(),
        realtime=PostgresNotifyPublisher(),
        transaction=SqlAlchemyTelemetryTransaction(db),
        steps=steps,
        items=items,
        manifests=manifests,
        estimates=estimates,
        projector=ProjectAutomationEvents(steps, items, manifests, estimates, _concluir_direta(db).execute),
    )
