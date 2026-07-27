from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.fleet.infrastructure.repositories import (
    SqlAlchemyAgentCapabilityRepository,
    SqlAlchemyAgentCommandRepository,
    SqlAlchemyAgentConfigurationRepository,
    SqlAlchemyAgentConnectionRepository,
    SqlAlchemyAgentCredentialRepository,
    SqlAlchemyAgentDiagnosticRepository,
    SqlAlchemyAgentInstanceRepository,
    SqlAlchemyAgentMachineProfileRepository,
    SqlAlchemyAgentPoolRepository,
    SqlAlchemyAgentRegistrationTokenRepository,
    SqlAlchemyAgentRepository,
    SqlAlchemyAgentResourceSnapshotRepository,
    SqlAlchemyFleetOutbox,
    SqlAlchemyFleetTransaction,
    SqlAlchemyInteractiveSessionRepository,
)
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.telemetry.infrastructure.repositories import SqlAlchemyInboxRepository


@dataclass(frozen=True)
class FleetAdapters:
    agents: SqlAlchemyAgentRepository
    instances: SqlAlchemyAgentInstanceRepository
    registration_tokens: SqlAlchemyAgentRegistrationTokenRepository
    credentials: SqlAlchemyAgentCredentialRepository
    profiles: SqlAlchemyAgentMachineProfileRepository
    snapshots: SqlAlchemyAgentResourceSnapshotRepository
    capabilities: SqlAlchemyAgentCapabilityRepository
    configurations: SqlAlchemyAgentConfigurationRepository
    pools: SqlAlchemyAgentPoolRepository
    interactive_sessions: SqlAlchemyInteractiveSessionRepository
    connections: SqlAlchemyAgentConnectionRepository
    diagnostics: SqlAlchemyAgentDiagnosticRepository
    commands: SqlAlchemyAgentCommandRepository
    inbox: SqlAlchemyInboxRepository
    audit: SqlAlchemyAuditEventRepository
    outbox: SqlAlchemyFleetOutbox
    transaction: SqlAlchemyFleetTransaction


def build_fleet_adapters(db: Session) -> FleetAdapters:
    return FleetAdapters(
        agents=SqlAlchemyAgentRepository(db),
        instances=SqlAlchemyAgentInstanceRepository(db),
        registration_tokens=SqlAlchemyAgentRegistrationTokenRepository(db),
        credentials=SqlAlchemyAgentCredentialRepository(db),
        profiles=SqlAlchemyAgentMachineProfileRepository(db),
        snapshots=SqlAlchemyAgentResourceSnapshotRepository(db),
        capabilities=SqlAlchemyAgentCapabilityRepository(db),
        configurations=SqlAlchemyAgentConfigurationRepository(db),
        pools=SqlAlchemyAgentPoolRepository(db),
        interactive_sessions=SqlAlchemyInteractiveSessionRepository(db),
        connections=SqlAlchemyAgentConnectionRepository(db),
        diagnostics=SqlAlchemyAgentDiagnosticRepository(db),
        commands=SqlAlchemyAgentCommandRepository(db),
        inbox=SqlAlchemyInboxRepository(db),
        audit=SqlAlchemyAuditEventRepository(db),
        outbox=SqlAlchemyFleetOutbox(db),
        transaction=SqlAlchemyFleetTransaction(db),
    )
