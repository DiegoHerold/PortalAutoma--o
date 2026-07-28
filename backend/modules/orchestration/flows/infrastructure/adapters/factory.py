from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.dispatch.infrastructure.repositories.sqlalchemy_dispatch import SqlAlchemyAutomationVersionReader
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.orchestration.flows.infrastructure.repositories import (
    SqlAlchemyFlowEdgeRepository,
    SqlAlchemyFlowExecutionRepository,
    SqlAlchemyFlowNodeExecutionRepository,
    SqlAlchemyFlowNodeRepository,
    SqlAlchemyFlowRepository,
    SqlAlchemyFlowVersionRepository,
)
from modules.orchestration.infrastructure.repositories import (
    SqlAlchemyExecutionRepository,
    SqlAlchemyOrchestrationOutbox,
    SqlAlchemyOrchestrationTransaction,
    SqlAlchemyTaskExecutionRepository,
)
from modules.shared.infrastructure.repositories.sqlalchemy_idempotency import SqlAlchemyIdempotencyStore


@dataclass(frozen=True)
class FlowAdapters:
    flows: SqlAlchemyFlowRepository
    versions: SqlAlchemyFlowVersionRepository
    nodes: SqlAlchemyFlowNodeRepository
    edges: SqlAlchemyFlowEdgeRepository
    flow_executions: SqlAlchemyFlowExecutionRepository
    node_executions: SqlAlchemyFlowNodeExecutionRepository
    executions: SqlAlchemyExecutionRepository
    tasks: SqlAlchemyTaskExecutionRepository
    automation_versions: SqlAlchemyAutomationVersionReader
    outbox: SqlAlchemyOrchestrationOutbox
    audit: SqlAlchemyAuditEventRepository
    idempotency: SqlAlchemyIdempotencyStore
    transaction: SqlAlchemyOrchestrationTransaction


def build_flow_adapters(db: Session) -> FlowAdapters:
    return FlowAdapters(
        flows=SqlAlchemyFlowRepository(db),
        versions=SqlAlchemyFlowVersionRepository(db),
        nodes=SqlAlchemyFlowNodeRepository(db),
        edges=SqlAlchemyFlowEdgeRepository(db),
        flow_executions=SqlAlchemyFlowExecutionRepository(db),
        node_executions=SqlAlchemyFlowNodeExecutionRepository(db),
        executions=SqlAlchemyExecutionRepository(db),
        tasks=SqlAlchemyTaskExecutionRepository(db),
        automation_versions=SqlAlchemyAutomationVersionReader(db),
        outbox=SqlAlchemyOrchestrationOutbox(db),
        audit=SqlAlchemyAuditEventRepository(db),
        idempotency=SqlAlchemyIdempotencyStore(db),
        transaction=SqlAlchemyOrchestrationTransaction(db),
    )
