from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.dispatch.application.use_cases import ScheduleTaskExecution
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.application.dto import ActorDTO, CreateAutomationExecutionCommand
from modules.orchestration.application.use_cases import CreateAutomationExecution, GetExecutionDetails
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters


def create_and_schedule_execution(
    db: Session,
    *,
    automation_version_id: int,
    actor: ActorDTO,
    parameters: dict[str, Any],
    priority: int,
    origin: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    request_hash: str | None = None,
):
    adapters = build_orchestration_adapters(db)
    details = CreateAutomationExecution(
        adapters.executions,
        adapters.tasks,
        adapters.attempts,
        adapters.offers,
        adapters.automation_versions,
        adapters.agent_selection,
        adapters.commands,
        adapters.outbox,
        adapters.audit,
        adapters.idempotency,
        adapters.transaction,
    ).execute(
        CreateAutomationExecutionCommand(
            automation_version_id=automation_version_id,
            actor=actor,
            parameters=parameters,
            priority=priority,
            origin=origin,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
    )
    if details.tasks:
        dispatch_adapters = build_dispatch_adapters(db)
        ScheduleTaskExecution(
            dispatch_adapters.ready_tasks,
            dispatch_adapters.attempts,
            dispatch_adapters.offers,
            dispatch_adapters.automation_versions,
            dispatch_adapters.candidates,
            dispatch_adapters.decisions,
            dispatch_adapters.reservations,
            dispatch_adapters.locks,
            dispatch_adapters.commands,
            dispatch_adapters.outbox,
            dispatch_adapters.transaction,
        ).execute(details.tasks[0].id)
        adapters = build_orchestration_adapters(db)
        details = GetExecutionDetails(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.offers,
            adapters.automation_versions,
            adapters.agent_selection,
        ).execute(details.execution.id)
    return details
