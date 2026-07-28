from __future__ import annotations

from workers.celery_app import celery_app
from infrastructure.database import SessionLocal
from modules.orchestration.flows.application import SynchronizeFlowNodeExecutions
from modules.orchestration.flows.infrastructure.adapters import build_flow_adapters


@celery_app.task(name="workers.tasks.flow_tasks.sync_flow_nodes")
def sync_flow_nodes() -> str:
    with SessionLocal() as db:
        adapters = build_flow_adapters(db)
        result = SynchronizeFlowNodeExecutions(
            adapters.versions,
            adapters.nodes,
            adapters.edges,
            adapters.flow_executions,
            adapters.node_executions,
            adapters.executions,
            adapters.tasks,
            adapters.automation_versions,
            adapters.outbox,
            adapters.transaction,
        ).execute()
    return f"updated={result['updated']}"
