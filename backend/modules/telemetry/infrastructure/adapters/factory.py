from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.telemetry.infrastructure.adapters.payload_validation import (
    DefaultEventPayloadValidator,
    RecursiveSecretMasker,
)
from modules.telemetry.infrastructure.realtime.broadcaster import execution_realtime_publisher
from modules.telemetry.infrastructure.repositories import (
    SqlAlchemyEventAcknowledgementRepository,
    SqlAlchemyExecutionAttemptTelemetryReader,
    SqlAlchemyExecutionEventRepository,
    SqlAlchemyExecutionMetricRepository,
    SqlAlchemyTelemetryTransaction,
)


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


def build_telemetry_adapters(db: Session) -> TelemetryAdapters:
    return TelemetryAdapters(
        attempts=SqlAlchemyExecutionAttemptTelemetryReader(db),
        events=SqlAlchemyExecutionEventRepository(db),
        acknowledgements=SqlAlchemyEventAcknowledgementRepository(db),
        metrics=SqlAlchemyExecutionMetricRepository(db),
        validator=DefaultEventPayloadValidator(),
        masker=RecursiveSecretMasker(),
        realtime=execution_realtime_publisher,
        transaction=SqlAlchemyTelemetryTransaction(db),
    )
