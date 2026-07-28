from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from modules.catalog.infrastructure.repositories import SqlAlchemyCatalogRepository
from modules.dispatch.application.use_cases import ScheduleTaskExecution
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.application.dto import ActorDTO, CreateAutomationExecutionCommand
from modules.orchestration.application.use_cases import CreateAutomationExecution, GetExecutionDetails
from modules.orchestration.flows.application import CreateFlowExecution
from modules.orchestration.flows.infrastructure.adapters import build_flow_adapters
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.orchestration.scheduling.application.dto import ScheduleDTO, ScheduleExecutionDTO


class ModuleScheduleExecutionCreator:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_execution(self, schedule: ScheduleDTO, schedule_execution: ScheduleExecutionDTO, actor: ActorDTO) -> dict:
        if schedule.target_type == "flow":
            return self._create_flow(schedule, schedule_execution, actor)
        return self._create_automation(schedule, schedule_execution, actor)

    def _create_flow(self, schedule: ScheduleDTO, schedule_execution: ScheduleExecutionDTO, actor: ActorDTO) -> dict:
        if not schedule.flow_version_id:
            raise ValueError("Flow schedule requires flow_version_id.")
        adapters = build_flow_adapters(self.db)
        details = CreateFlowExecution(
            adapters.flows,
            adapters.versions,
            adapters.nodes,
            adapters.edges,
            adapters.flow_executions,
            adapters.node_executions,
            adapters.executions,
            adapters.tasks,
            adapters.automation_versions,
            adapters.outbox,
            adapters.audit,
            adapters.transaction,
        ).execute(
            flow_version_id=schedule.flow_version_id,
            actor=actor,
            input=schedule.payload,
            origin="schedule",
            schedule_execution_id=schedule_execution.id,
            correlation_id=schedule_execution.id,
        )
        return {"execution_id": details.flow_execution.execution_id, "flow_execution_id": details.flow_execution.id, "target_type": "flow"}

    def _create_automation(self, schedule: ScheduleDTO, schedule_execution: ScheduleExecutionDTO, actor: ActorDTO) -> dict:
        version_id = schedule.automation_version_id
        if version_id is None:
            if schedule.automation_id is None:
                raise ValueError("Automation schedule requires automation_id or automation_version_id.")
            latest = SqlAlchemyCatalogRepository(self.db).get_latest_published_version(schedule.automation_id)
            if latest is None:
                raise ValueError("Automation does not have a published version.")
            version_id = latest.id
        adapters = build_orchestration_adapters(self.db)
        command_payload = {
            "schedule_id": schedule.id,
            "schedule_execution_id": schedule_execution.id,
            "automation_version_id": version_id,
            "payload": schedule.payload,
        }
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
                automation_version_id=int(version_id),
                actor=actor,
                parameters=schedule.payload,
                priority=0,
                origin="schedule",
                correlation_id=schedule_execution.id,
                idempotency_key=f"schedule:{schedule.id}:{schedule_execution.scheduled_for.isoformat()}",
                request_hash=hashlib.sha256(json.dumps(command_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
            )
        )
        if details.tasks:
            dispatch_adapters = build_dispatch_adapters(self.db)
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
            adapters = build_orchestration_adapters(self.db)
            details = GetExecutionDetails(
                adapters.executions,
                adapters.tasks,
                adapters.attempts,
                adapters.offers,
                adapters.automation_versions,
                adapters.agent_selection,
            ).execute(details.execution.id)
        return {"execution_id": details.execution.id, "flow_execution_id": None, "target_type": "automation"}
