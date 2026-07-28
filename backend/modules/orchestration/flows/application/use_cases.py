from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent
from modules.orchestration.application.dto import ActorDTO, ExecutionDTO, TaskExecutionDTO
from modules.orchestration.application.ports import AutomationVersionReader, ExecutionRepository, OutboxPort, TaskExecutionRepository, TransactionManager
from modules.orchestration.domain.execution import Execution
from modules.orchestration.domain.states import ExecutionOrigin, ExecutionType
from modules.orchestration.domain.task_execution import TaskExecution
from modules.orchestration.flows.application.dto import (
    FlowDTO,
    FlowEdgeDTO,
    FlowExecutionDetailsDTO,
    FlowExecutionDTO,
    FlowNodeDTO,
    FlowNodeExecutionDTO,
    FlowValidationIssueDTO,
    FlowValidationResultDTO,
    FlowVersionDTO,
)
from modules.orchestration.flows.application.ports import (
    FlowEdgeRepository,
    FlowExecutionRepository,
    FlowNodeExecutionRepository,
    FlowNodeRepository,
    FlowRepository,
    FlowVersionRepository,
)
from modules.orchestration.flows.domain import MappingError, evaluate_condition, resolve_mapping, validate_dag


TERMINAL_NODE_STATUSES = {"succeeded", "failed", "cancelled", "timed_out", "skipped"}
TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled", "timed_out", "skipped"}
ACTIVE_FLOW_STATUSES = {"created", "pending", "running", "cancelling"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class CreateFlow:
    def __init__(self, flows: FlowRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.flows = flows
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, *, key: str, name: str, actor: ActorDTO, description: str | None = None, category_id: int | None = None, tags: list[str] | None = None) -> FlowDTO:
        if self.flows.get_by_key(key):
            raise ValueError("Flow key already exists.")
        now = utcnow()
        flow = self.flows.add(FlowDTO(id=new_id("flo"), key=key, name=name, description=description, category_id=category_id, tags=tags or [], status="draft", created_by=actor.actor_id, created_at=now, updated_at=now))
        self.outbox.append_event("flow.created", "flow", flow.id, {"flow_id": flow.id})
        _audit(self.audit, actor, "flow.created", "flow", flow.id, after={"key": key})
        self.transaction.commit()
        return flow


class UpdateFlowMetadata:
    def __init__(self, flows: FlowRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.flows = flows
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, flow_id: str, *, actor: ActorDTO, payload: dict[str, Any]) -> FlowDTO:
        flow = _require_flow(self.flows, flow_id)
        updated = self.flows.save(
            replace(
                flow,
                name=str(payload.get("name") or flow.name),
                description=payload.get("description", flow.description),
                category_id=payload.get("category_id", flow.category_id),
                tags=list(payload.get("tags") or flow.tags),
                status=str(payload.get("status") or flow.status),
                updated_at=utcnow(),
            )
        )
        self.outbox.append_event("flow.updated", "flow", flow.id, {"flow_id": flow.id})
        _audit(self.audit, actor, "flow.updated", "flow", flow.id)
        self.transaction.commit()
        return updated


class ArchiveFlow:
    def __init__(self, flows: FlowRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.flows = flows
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, flow_id: str, *, actor: ActorDTO) -> FlowDTO:
        flow = _require_flow(self.flows, flow_id)
        archived = self.flows.save(replace(flow, status="archived", updated_at=utcnow()))
        self.outbox.append_event("flow.archived", "flow", flow.id, {"flow_id": flow.id})
        _audit(self.audit, actor, "flow.archived", "flow", flow.id)
        self.transaction.commit()
        return archived


class ListFlows:
    def __init__(self, flows: FlowRepository) -> None:
        self.flows = flows

    def execute(self, limit: int = 100, offset: int = 0) -> list[FlowDTO]:
        return self.flows.list(limit=limit, offset=offset)


class GetFlow:
    def __init__(self, flows: FlowRepository) -> None:
        self.flows = flows

    def execute(self, flow_id: str) -> FlowDTO:
        return _require_flow(self.flows, flow_id)


class CreateFlowVersion:
    def __init__(self, flows: FlowRepository, versions: FlowVersionRepository, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.flows = flows
        self.versions = versions
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, flow_id: str, *, version: str, actor: ActorDTO, definition: dict[str, Any] | None = None, input_schema: dict[str, Any] | None = None, output_schema: dict[str, Any] | None = None, release_notes: str | None = None) -> FlowVersionDTO:
        flow = _require_flow(self.flows, flow_id)
        if flow.status == "archived":
            raise ValueError("Archived Flow cannot receive new versions.")
        if not SEMVER_RE.match(version):
            raise ValueError("FlowVersion must use SemVer.")
        if any(item.version == version for item in self.versions.list_for_flow(flow_id)):
            raise ValueError("FlowVersion already exists for this Flow.")
        row = self.versions.add(FlowVersionDTO(id=new_id("flv"), flow_id=flow_id, version=version, status="draft", definition=definition or {}, input_schema=input_schema, output_schema=output_schema, release_notes=release_notes, created_by=actor.actor_id, created_at=utcnow()))
        self.outbox.append_event("flow_version.created", "flow_version", row.id, {"flow_version_id": row.id})
        _audit(self.audit, actor, "flow_version.created", "flow_version", row.id, after={"flow_id": flow_id, "version": version})
        self.transaction.commit()
        return row


class UpdateDraftFlowVersion:
    def __init__(self, versions: FlowVersionRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.transaction = transaction

    def execute(self, flow_version_id: str, payload: dict[str, Any]) -> FlowVersionDTO:
        version = _require_version(self.versions, flow_version_id)
        _ensure_version_mutable(version)
        updated = self.versions.save(
            replace(
                version,
                definition=payload.get("definition", version.definition) or {},
                input_schema=payload.get("input_schema", version.input_schema),
                output_schema=payload.get("output_schema", version.output_schema),
                release_notes=payload.get("release_notes", version.release_notes),
            )
        )
        self.transaction.commit()
        return updated


class AddFlowNode:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.nodes = nodes
        self.transaction = transaction

    def execute(self, flow_version_id: str, payload: dict[str, Any]) -> FlowNodeDTO:
        version = _require_version(self.versions, flow_version_id)
        _ensure_version_mutable(version)
        if any(item.key == payload["key"] for item in self.nodes.list_for_version(flow_version_id)):
            raise ValueError("FlowNode key already exists in this FlowVersion.")
        node = self.nodes.add(_node_from_payload(flow_version_id, payload))
        self.transaction.commit()
        return node


class UpdateFlowNode:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.nodes = nodes
        self.transaction = transaction

    def execute(self, node_id: str, payload: dict[str, Any]) -> FlowNodeDTO:
        node = _require_node(self.nodes, node_id)
        version = _require_version(self.versions, node.flow_version_id)
        _ensure_version_mutable(version)
        updated = self.nodes.save(
            replace(
                node,
                name=str(payload.get("name") or node.name),
                node_type=str(payload.get("node_type") or node.node_type),
                automation_version_id=payload.get("automation_version_id", node.automation_version_id),
                configuration=payload.get("configuration", node.configuration) or {},
                input_mapping=payload.get("input_mapping", node.input_mapping) or {},
                output_mapping=payload.get("output_mapping", node.output_mapping) or {},
                condition=payload.get("condition", node.condition),
                retry_policy=payload.get("retry_policy", node.retry_policy) or {},
                timeout_policy=payload.get("timeout_policy", node.timeout_policy) or {},
                failure_policy=str(payload.get("failure_policy") or node.failure_policy),
                execution_policy=payload.get("execution_policy", node.execution_policy) or {},
                position_metadata=payload.get("position_metadata", node.position_metadata) or {},
            )
        )
        self.transaction.commit()
        return updated


class RemoveFlowNode:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, edges: FlowEdgeRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.transaction = transaction

    def execute(self, node_id: str) -> None:
        node = _require_node(self.nodes, node_id)
        version = _require_version(self.versions, node.flow_version_id)
        _ensure_version_mutable(version)
        for edge in self.edges.list_for_version(version.id):
            if edge.source_node_id == node_id or edge.target_node_id == node_id:
                self.edges.remove(edge.id)
        self.nodes.remove(node_id)
        self.transaction.commit()


class AddFlowEdge:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, edges: FlowEdgeRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.transaction = transaction

    def execute(self, flow_version_id: str, payload: dict[str, Any]) -> FlowEdgeDTO:
        version = _require_version(self.versions, flow_version_id)
        _ensure_version_mutable(version)
        source = _require_node(self.nodes, payload["source_node_id"])
        target = _require_node(self.nodes, payload["target_node_id"])
        if source.flow_version_id != flow_version_id or target.flow_version_id != flow_version_id:
            raise ValueError("FlowEdge nodes must belong to the same FlowVersion.")
        edge = self.edges.add(
            FlowEdgeDTO(
                id=new_id("fle"),
                flow_version_id=flow_version_id,
                source_node_id=source.id,
                target_node_id=target.id,
                edge_type=str(payload.get("edge_type") or "success"),
                condition=payload.get("condition"),
                mapping=payload.get("mapping") or {},
                created_at=utcnow(),
            )
        )
        self.transaction.commit()
        return edge


class RemoveFlowEdge:
    def __init__(self, versions: FlowVersionRepository, edges: FlowEdgeRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.edges = edges
        self.transaction = transaction

    def execute(self, edge_id: str) -> None:
        edge = self.edges.get(edge_id)
        if edge is None:
            return
        version = _require_version(self.versions, edge.flow_version_id)
        _ensure_version_mutable(version)
        self.edges.remove(edge_id)
        self.transaction.commit()


class ValidateFlowVersion:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, edges: FlowEdgeRepository, automation_versions: AutomationVersionReader) -> None:
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.automation_versions = automation_versions

    def execute(self, flow_version_id: str) -> FlowValidationResultDTO:
        version = _require_version(self.versions, flow_version_id)
        if not SEMVER_RE.match(version.version):
            return FlowValidationResultDTO(False, [FlowValidationIssueDTO("FLOW_VERSION_SEMVER_INVALID", "FlowVersion deve usar SemVer.")])
        nodes = self.nodes.list_for_version(flow_version_id)
        edges = self.edges.list_for_version(flow_version_id)
        result = validate_dag(nodes, edges)
        issues = list(result.issues)
        if not nodes:
            issues.append(FlowValidationIssueDTO("FLOW_NODE_MISSING", "FlowVersion precisa possuir ao menos um no."))
        valid_node_types = {"automation", "condition", "join"}
        valid_edge_types = {"success", "failure", "always", "conditional"}
        for node in nodes:
            if node.node_type not in valid_node_types:
                issues.append(FlowValidationIssueDTO("FLOW_NODE_TYPE_INVALID", "Tipo de no invalido.", {"node_id": node.id, "node_type": node.node_type}))
            if node.failure_policy not in {"fail_flow", "continue", "skip_dependents", "continue_alternative_path"}:
                issues.append(FlowValidationIssueDTO("FLOW_FAILURE_POLICY_INVALID", "FailurePolicy invalida.", {"node_id": node.id, "failure_policy": node.failure_policy}))
            if node.node_type == "automation":
                if not node.automation_version_id:
                    issues.append(FlowValidationIssueDTO("FLOW_NODE_AUTOMATION_VERSION_MISSING", "No de automacao precisa de AutomationVersion.", {"node_id": node.id}))
                elif self.automation_versions.get_published_snapshot(int(node.automation_version_id)) is None:
                    issues.append(FlowValidationIssueDTO("FLOW_NODE_AUTOMATION_VERSION_UNAVAILABLE", "AutomationVersion precisa existir e estar publicada.", {"node_id": node.id, "automation_version_id": node.automation_version_id}))
            elif node.automation_version_id is not None:
                issues.append(FlowValidationIssueDTO("FLOW_NODE_AUTOMATION_VERSION_NOT_ALLOWED", "Apenas no automation deve referenciar AutomationVersion.", {"node_id": node.id}))
        for edge in edges:
            if edge.edge_type not in valid_edge_types:
                issues.append(FlowValidationIssueDTO("FLOW_EDGE_TYPE_INVALID", "Tipo de aresta invalido.", {"edge_id": edge.id, "edge_type": edge.edge_type}))
        return FlowValidationResultDTO(valid=not issues, issues=issues, topological_order=result.topological_order)


class PublishFlowVersion:
    def __init__(self, flows: FlowRepository, versions: FlowVersionRepository, nodes: FlowNodeRepository, edges: FlowEdgeRepository, automation_versions: AutomationVersionReader, outbox: OutboxPort, audit, transaction: TransactionManager) -> None:
        self.flows = flows
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.automation_versions = automation_versions
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, flow_version_id: str, *, actor: ActorDTO) -> FlowVersionDTO:
        version = _require_version(self.versions, flow_version_id)
        flow = _require_flow(self.flows, version.flow_id)
        if flow.status == "archived":
            raise ValueError("Archived FlowVersion cannot be published.")
        result = ValidateFlowVersion(self.versions, self.nodes, self.edges, self.automation_versions).execute(flow_version_id)
        if not result.valid:
            raise ValueError({"code": "FLOW_VERSION_INVALID", "issues": [issue.__dict__ for issue in result.issues]})
        now = utcnow()
        published = self.versions.save(replace(version, status="published", published_by=actor.actor_id, published_at=now))
        if flow.status == "draft":
            self.flows.save(replace(flow, status="active", updated_at=now))
        self.outbox.append_event("flow_version.published", "flow_version", version.id, {"flow_version_id": version.id})
        _audit(self.audit, actor, "flow_version.published", "flow_version", version.id)
        self.transaction.commit()
        return published


class DeprecateFlowVersion:
    def __init__(self, versions: FlowVersionRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.transaction = transaction

    def execute(self, flow_version_id: str) -> FlowVersionDTO:
        version = _require_version(self.versions, flow_version_id)
        saved = self.versions.save(replace(version, status="deprecated", deprecated_at=utcnow()))
        self.transaction.commit()
        return saved


class BlockFlowVersion:
    def __init__(self, versions: FlowVersionRepository, transaction: TransactionManager) -> None:
        self.versions = versions
        self.transaction = transaction

    def execute(self, flow_version_id: str) -> FlowVersionDTO:
        version = _require_version(self.versions, flow_version_id)
        saved = self.versions.save(replace(version, status="blocked", blocked_at=utcnow()))
        self.transaction.commit()
        return saved


class CreateFlowExecution:
    def __init__(
        self,
        flows: FlowRepository,
        versions: FlowVersionRepository,
        nodes: FlowNodeRepository,
        edges: FlowEdgeRepository,
        flow_executions: FlowExecutionRepository,
        node_executions: FlowNodeExecutionRepository,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        automation_versions: AutomationVersionReader,
        outbox: OutboxPort,
        audit,
        transaction: TransactionManager,
    ) -> None:
        self.flows = flows
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.flow_executions = flow_executions
        self.node_executions = node_executions
        self.executions = executions
        self.tasks = tasks
        self.automation_versions = automation_versions
        self.outbox = outbox
        self.audit = audit
        self.transaction = transaction

    def execute(self, *, flow_version_id: str, actor: ActorDTO, input: dict[str, Any] | None = None, origin: str = "manual", schedule_execution_id: str | None = None, correlation_id: str | None = None) -> FlowExecutionDetailsDTO:
        version = _require_version(self.versions, flow_version_id)
        if version.status != "published":
            raise ValueError("FlowVersion must be published to execute.")
        flow = _require_flow(self.flows, version.flow_id)
        if flow.status in {"disabled", "archived"}:
            raise ValueError("Flow is not executable.")
        nodes = self.nodes.list_for_version(version.id)
        edges = self.edges.list_for_version(version.id)
        validation = ValidateFlowVersion(self.versions, self.nodes, self.edges, self.automation_versions).execute(version.id)
        if not validation.valid:
            raise ValueError({"code": "FLOW_VERSION_INVALID", "issues": [issue.__dict__ for issue in validation.issues]})
        now = utcnow()
        execution = Execution.create(
            id=new_id("exe"),
            type=ExecutionType.FLOW,
            origin=ExecutionOrigin(origin),
            requested_by=actor.actor_id,
            organization_id=None,
            input={"flow_version_id": version.id, "input": input or {}},
            correlation_id=correlation_id,
            idempotency_key=None,
            now=now,
        ).mark_pending().mark_running(now)
        execution_dto = self.executions.add(_execution_to_dto(execution))
        flow_execution = self.flow_executions.add(
            FlowExecutionDTO(
                id=new_id("flx"),
                execution_id=execution.id,
                flow_version_id=version.id,
                status="pending",
                origin=origin,
                input=input or {},
                output=None,
                requested_by=actor.actor_id,
                schedule_execution_id=schedule_execution_id,
                correlation_id=correlation_id,
                created_at=now,
            )
        )
        for node in nodes:
            self.node_executions.add(FlowNodeExecutionDTO(id=new_id("fnx"), flow_execution_id=flow_execution.id, flow_node_id=node.id, status="pending", input={}, output=None, condition_result=None, dependency_state={}, revision=1))
        self.outbox.append_event("flow_execution.created", "flow_execution", flow_execution.id, {"flow_execution_id": flow_execution.id, "execution_id": execution.id}, correlation_id)
        _audit(self.audit, actor, "flow_execution.created", "flow_execution", flow_execution.id, after={"flow_version_id": version.id})
        flow_execution = _release_ready_nodes(flow_execution, nodes, edges, self.node_executions, self.tasks, self.automation_versions, self.outbox)
        flow_execution = _recalculate_flow_status(flow_execution, version, nodes, self.node_executions, self.flow_executions, self.executions, self.outbox)
        self.flow_executions.save(flow_execution)
        self.transaction.commit()
        return _details(flow_execution, execution_dto, version, nodes, edges, self.node_executions)


class SynchronizeFlowNodeExecutions:
    def __init__(
        self,
        versions: FlowVersionRepository,
        nodes: FlowNodeRepository,
        edges: FlowEdgeRepository,
        flow_executions: FlowExecutionRepository,
        node_executions: FlowNodeExecutionRepository,
        executions: ExecutionRepository,
        tasks: TaskExecutionRepository,
        automation_versions: AutomationVersionReader,
        outbox: OutboxPort,
        transaction: TransactionManager,
    ) -> None:
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.flow_executions = flow_executions
        self.node_executions = node_executions
        self.executions = executions
        self.tasks = tasks
        self.automation_versions = automation_versions
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, limit: int = 100) -> dict[str, int]:
        updated = 0
        for node_execution in self.node_executions.list_active(limit=limit):
            if not node_execution.task_execution_id:
                continue
            task = self.tasks.get(node_execution.task_execution_id)
            if task is None or task.status not in TERMINAL_TASK_STATUSES:
                continue
            flow_execution = self.flow_executions.get(node_execution.flow_execution_id)
            if flow_execution is None or flow_execution.status not in ACTIVE_FLOW_STATUSES:
                continue
            version = self.versions.get(flow_execution.flow_version_id)
            if version is None:
                continue
            if _flow_timed_out(flow_execution, version, now=utcnow()):
                _timeout_flow(flow_execution, self.node_executions, self.flow_executions, self.executions, self.outbox)
                updated += 1
                continue
            node = self.nodes.get(node_execution.flow_node_id)
            if node is None:
                continue
            now = utcnow()
            status = _node_status_from_task(task.status)
            saved = self.node_executions.save(
                replace(
                    node_execution,
                    status=status,
                    output=task.result,
                    completed_at=now,
                    failure_summary=task.failure_summary,
                    revision=node_execution.revision + 1,
                )
            )
            event_status = "completed" if status == "succeeded" else status
            self.outbox.append_event(f"flow_node.{event_status}", "flow_node_execution", saved.id, {"flow_node_execution_id": saved.id, "task_execution_id": task.id})
            updated += 1
            nodes = self.nodes.list_for_version(flow_execution.flow_version_id)
            edges = self.edges.list_for_version(flow_execution.flow_version_id)
            if status in {"failed", "cancelled", "timed_out"} and node.failure_policy == "fail_flow":
                flow_execution = _finish_flow(flow_execution, self.flow_executions, self.executions, status="failed", output=None, summary=saved.failure_summary or "Flow node failed.", outbox=self.outbox)
                continue
            if status in {"failed", "cancelled", "timed_out"} and node.failure_policy == "skip_dependents":
                _skip_dependents(node.id, nodes, edges, flow_execution.id, self.node_executions, "Skipped by failure_policy=skip_dependents.")
            flow_execution = _release_ready_nodes(flow_execution, nodes, edges, self.node_executions, self.tasks, self.automation_versions, self.outbox)
            flow_execution = _recalculate_flow_status(flow_execution, version, nodes, self.node_executions, self.flow_executions, self.executions, self.outbox)
            self.flow_executions.save(flow_execution)
        self.transaction.commit()
        return {"updated": updated}


class GetFlowExecution:
    def __init__(self, versions: FlowVersionRepository, nodes: FlowNodeRepository, edges: FlowEdgeRepository, flow_executions: FlowExecutionRepository, node_executions: FlowNodeExecutionRepository, executions: ExecutionRepository) -> None:
        self.versions = versions
        self.nodes = nodes
        self.edges = edges
        self.flow_executions = flow_executions
        self.node_executions = node_executions
        self.executions = executions

    def execute(self, flow_execution_id: str) -> FlowExecutionDetailsDTO:
        flow_execution = _require_flow_execution(self.flow_executions, flow_execution_id)
        version = self.versions.get(flow_execution.flow_version_id)
        execution = self.executions.get(flow_execution.execution_id)
        nodes = self.nodes.list_for_version(flow_execution.flow_version_id)
        edges = self.edges.list_for_version(flow_execution.flow_version_id)
        return FlowExecutionDetailsDTO(flow_execution=flow_execution, execution=execution.__dict__ if execution else None, flow_version=version, nodes=nodes, edges=edges, node_executions=self.node_executions.list_for_flow_execution(flow_execution.id))


class ListFlowExecutions:
    def __init__(self, flow_executions: FlowExecutionRepository) -> None:
        self.flow_executions = flow_executions

    def execute(self, limit: int = 100, offset: int = 0) -> list[FlowExecutionDTO]:
        return self.flow_executions.list(limit=limit, offset=offset)


class CancelFlowExecution:
    def __init__(self, flow_executions: FlowExecutionRepository, node_executions: FlowNodeExecutionRepository, executions: ExecutionRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.flow_executions = flow_executions
        self.node_executions = node_executions
        self.executions = executions
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, flow_execution_id: str, *, reason: str | None = None) -> FlowExecutionDTO:
        flow_execution = _require_flow_execution(self.flow_executions, flow_execution_id)
        now = utcnow()
        for item in self.node_executions.list_for_flow_execution(flow_execution.id):
            if item.status not in TERMINAL_NODE_STATUSES:
                self.node_executions.save(replace(item, status="cancelled", completed_at=now, failure_summary=reason or "FlowExecution cancelled."))
        saved = self.flow_executions.save(replace(flow_execution, status="cancelled", cancellation_requested_at=now, completed_at=now, failure_summary=reason))
        execution = self.executions.get(flow_execution.execution_id)
        if execution is not None:
            self.executions.save(replace(execution, status="cancelled", completed_at=now, failure_summary=reason))
        self.outbox.append_event("flow_execution.cancelled", "flow_execution", flow_execution.id, {"flow_execution_id": flow_execution.id})
        self.transaction.commit()
        return saved


ReleaseFlowNode = SynchronizeFlowNodeExecutions
CompleteFlowNode = SynchronizeFlowNodeExecutions
FailFlowNode = SynchronizeFlowNodeExecutions
SkipFlowNode = SynchronizeFlowNodeExecutions
EvaluateReadyFlowNodes = SynchronizeFlowNodeExecutions
CalculateFlowExecutionStatus = SynchronizeFlowNodeExecutions


def _release_ready_nodes(flow_execution: FlowExecutionDTO, nodes: list[FlowNodeDTO], edges: list[FlowEdgeDTO], node_executions: FlowNodeExecutionRepository, tasks: TaskExecutionRepository, automation_versions: AutomationVersionReader, outbox: OutboxPort) -> FlowExecutionDTO:
    changed = True
    current = flow_execution
    while changed:
        changed = False
        executions = node_executions.list_for_flow_execution(current.id)
        by_node = {item.flow_node_id: item for item in executions}
        context = _context(current, nodes, executions)
        for node in nodes:
            node_execution = by_node.get(node.id)
            if node_execution is None or node_execution.status not in {"pending", "blocked"}:
                continue
            decision = _dependency_decision(node, edges, by_node, context)
            if decision["status"] == "waiting":
                continue
            if decision["status"] == "skipped":
                node_executions.save(replace(node_execution, status="skipped", condition_result=decision, dependency_state=decision, skipped_at=utcnow(), revision=node_execution.revision + 1))
                outbox.append_event("flow_node.skipped", "flow_node_execution", node_execution.id, {"flow_node_execution_id": node_execution.id, "flow_node_id": node.id})
                changed = True
                continue
            try:
                condition = evaluate_condition(node.condition, context)
                if not condition["matched"]:
                    node_executions.save(replace(node_execution, status="skipped", condition_result=condition, dependency_state=decision, skipped_at=utcnow(), revision=node_execution.revision + 1))
                    outbox.append_event("flow_node.skipped", "flow_node_execution", node_execution.id, {"flow_node_execution_id": node_execution.id, "flow_node_id": node.id})
                    changed = True
                    continue
                node_input = resolve_mapping(node.input_mapping, context)
            except MappingError as exc:
                node_executions.save(replace(node_execution, status="failed", condition_result={"code": exc.code, "details": exc.details}, dependency_state=decision, completed_at=utcnow(), failure_summary=str(exc), revision=node_execution.revision + 1))
                outbox.append_event("flow_node.failed", "flow_node_execution", node_execution.id, {"flow_node_execution_id": node_execution.id, "flow_node_id": node.id, "code": exc.code})
                changed = True
                continue
            if node.node_type == "automation":
                task = _create_task_for_node(current, node, node_input, tasks, automation_versions)
                node_executions.save(replace(node_execution, status="running", input=node_input, condition_result=condition, dependency_state=decision, task_execution_id=task.id, started_at=utcnow(), revision=node_execution.revision + 1))
                outbox.append_event("flow_node.started", "flow_node_execution", node_execution.id, {"flow_node_execution_id": node_execution.id, "flow_node_id": node.id, "task_execution_id": task.id})
            else:
                node_executions.save(replace(node_execution, status="succeeded", input=node_input, output=node_input, condition_result=condition, dependency_state=decision, started_at=utcnow(), completed_at=utcnow(), revision=node_execution.revision + 1))
                outbox.append_event("flow_node.completed", "flow_node_execution", node_execution.id, {"flow_node_execution_id": node_execution.id, "flow_node_id": node.id})
            if current.status in {"created", "pending"}:
                current = replace(current, status="running", started_at=current.started_at or utcnow())
            changed = True
    return current


def _create_task_for_node(flow_execution: FlowExecutionDTO, node: FlowNodeDTO, node_input: dict[str, Any], tasks: TaskExecutionRepository, automation_versions: AutomationVersionReader) -> TaskExecutionDTO:
    if not node.automation_version_id:
        raise ValueError("Automation FlowNode requires automation_version_id.")
    version = automation_versions.get_published_snapshot(int(node.automation_version_id))
    if version is None:
        raise ValueError("AutomationVersion is not executable.")
    now = utcnow()
    priority = int(node.execution_policy.get("priority") or 0)
    task = TaskExecution.create(
        id=new_id("task"),
        execution_id=flow_execution.execution_id,
        automation_version_id=version.automation_version_id,
        priority=priority,
        parameters=node_input,
        input={"parameters": node_input, "flow_execution_id": flow_execution.id, "flow_node_id": node.id},
        timeout_seconds=version.timeout_seconds,
        requirements_snapshot=_requirements_snapshot(version, flow_execution.execution_id, priority, node),
        retry_policy=node.retry_policy or version.retry_policy or {"max_attempts": 1, "max_retries": 0},
        timeout_policy=node.timeout_policy or version.timeout_policy or {"execution_timeout_seconds": version.timeout_seconds},
        now=now,
    ).mark_ready(now).mark_queued(now)
    return tasks.add(_task_to_dto(task))


def _dependency_decision(node: FlowNodeDTO, edges: list[FlowEdgeDTO], by_node: dict[str, FlowNodeExecutionDTO], context: dict[str, Any]) -> dict[str, Any]:
    incoming = [edge for edge in edges if edge.target_node_id == node.id]
    if not incoming:
        return {"status": "ready", "mode": "initial"}
    states: list[dict[str, Any]] = []
    satisfied = 0
    terminal = 0
    for edge in incoming:
        source = by_node.get(edge.source_node_id)
        state = {"edge_id": edge.id, "source_node_id": edge.source_node_id, "edge_type": edge.edge_type, "source_status": source.status if source else None, "satisfied": False}
        if source and source.status in TERMINAL_NODE_STATUSES:
            terminal += 1
            state["satisfied"] = _edge_satisfied(edge, source, context)
            if state["satisfied"]:
                satisfied += 1
        states.append(state)
    policy = str(node.execution_policy.get("dependency_policy") or "all")
    if policy == "any" and satisfied > 0:
        return {"status": "ready", "policy": policy, "dependencies": states}
    if policy == "all" and satisfied == len(incoming):
        return {"status": "ready", "policy": policy, "dependencies": states}
    if terminal == len(incoming):
        return {"status": "skipped", "policy": policy, "dependencies": states, "reason": "dependencies_not_satisfied"}
    return {"status": "waiting", "policy": policy, "dependencies": states}


def _edge_satisfied(edge: FlowEdgeDTO, source: FlowNodeExecutionDTO, context: dict[str, Any]) -> bool:
    if edge.edge_type == "success":
        return source.status == "succeeded"
    if edge.edge_type == "failure":
        return source.status in {"failed", "timed_out", "cancelled"}
    if edge.edge_type == "always":
        return source.status in TERMINAL_NODE_STATUSES
    if edge.edge_type == "conditional":
        return source.status == "succeeded" and evaluate_condition(edge.condition, context)["matched"]
    return False


def _skip_dependents(node_id: str, nodes: list[FlowNodeDTO], edges: list[FlowEdgeDTO], flow_execution_id: str, node_executions: FlowNodeExecutionRepository, reason: str) -> None:
    targets = {edge.target_node_id for edge in edges if edge.source_node_id == node_id}
    by_node = {item.flow_node_id: item for item in node_executions.list_for_flow_execution(flow_execution_id)}
    while targets:
        target = targets.pop()
        execution = by_node.get(target)
        if execution and execution.status not in TERMINAL_NODE_STATUSES:
            node_executions.save(replace(execution, status="skipped", skipped_at=utcnow(), failure_summary=reason, revision=execution.revision + 1))
        targets.update(edge.target_node_id for edge in edges if edge.source_node_id == target)


def _recalculate_flow_status(flow_execution: FlowExecutionDTO, version: FlowVersionDTO, nodes: list[FlowNodeDTO], node_executions: FlowNodeExecutionRepository, flow_executions: FlowExecutionRepository, executions: ExecutionRepository, outbox: OutboxPort) -> FlowExecutionDTO:
    executions_list = node_executions.list_for_flow_execution(flow_execution.id)
    if len(executions_list) < len(nodes):
        return flow_execution
    if any(item.status not in TERMINAL_NODE_STATUSES for item in executions_list):
        return flow_execution
    output, output_error = _flow_output(nodes, executions_list, flow_execution, version)
    if output_error:
        return _finish_flow(flow_execution, flow_executions, executions, status="failed", output=output, summary=output_error, outbox=outbox)
    if any(item.status == "failed" for item in executions_list):
        return _finish_flow(flow_execution, flow_executions, executions, status="partially_succeeded" if any(item.status == "succeeded" for item in executions_list) else "failed", output=output, summary="One or more Flow nodes failed.", outbox=outbox)
    return _finish_flow(flow_execution, flow_executions, executions, status="succeeded", output=output, summary=None, outbox=outbox)


def _finish_flow(flow_execution: FlowExecutionDTO, flow_executions: FlowExecutionRepository, executions: ExecutionRepository, *, status: str, output: dict[str, Any] | None, summary: str | None, outbox: OutboxPort) -> FlowExecutionDTO:
    now = utcnow()
    saved = flow_executions.save(replace(flow_execution, status=status, output=output, completed_at=flow_execution.completed_at or now, failure_summary=summary))
    execution = executions.get(flow_execution.execution_id)
    if execution is not None:
        executions.save(replace(execution, status=status, result=output, completed_at=execution.completed_at or now, failure_summary=summary))
    outbox.append_event(f"flow_execution.{status}", "flow_execution", flow_execution.id, {"flow_execution_id": flow_execution.id})
    return saved


def _flow_output(nodes: list[FlowNodeDTO], executions: list[FlowNodeExecutionDTO], flow_execution: FlowExecutionDTO, version: FlowVersionDTO) -> tuple[dict[str, Any], str | None]:
    context = _context(flow_execution, nodes, executions)
    node_output = {"nodes": {node.key: (next((item.output for item in executions if item.flow_node_id == node.id), None)) for node in nodes}}
    configured_mapping = (version.definition or {}).get("output_mapping")
    if not configured_mapping:
        return ((flow_execution.output or {}) | node_output), None
    try:
        mapped_output = resolve_mapping(configured_mapping, context)
    except MappingError as exc:
        return ((flow_execution.output or {}) | node_output | {"output_mapping_error": {"code": exc.code, "details": exc.details}}), f"Flow output mapping failed: {exc}"
    return ((flow_execution.output or {}) | {"output": mapped_output} | node_output), None


def _flow_timed_out(flow_execution: FlowExecutionDTO, version: FlowVersionDTO, *, now: datetime) -> bool:
    timeout_seconds = _positive_int((version.definition or {}).get("flow_timeout_seconds"))
    if timeout_seconds is None:
        return False
    started_at = flow_execution.started_at or flow_execution.created_at
    return (started_at is not None) and (started_at.timestamp() + timeout_seconds <= now.timestamp())


def _timeout_flow(flow_execution: FlowExecutionDTO, node_executions: FlowNodeExecutionRepository, flow_executions: FlowExecutionRepository, executions: ExecutionRepository, outbox: OutboxPort) -> FlowExecutionDTO:
    now = utcnow()
    for item in node_executions.list_for_flow_execution(flow_execution.id):
        if item.status not in TERMINAL_NODE_STATUSES:
            node_executions.save(replace(item, status="timed_out", completed_at=now, failure_summary="Flow timeout exceeded.", revision=item.revision + 1))
    saved = flow_executions.save(replace(flow_execution, status="timed_out", completed_at=now, failure_summary="Flow timeout exceeded."))
    execution = executions.get(flow_execution.execution_id)
    if execution is not None:
        executions.save(replace(execution, status="timed_out", completed_at=now, failure_summary="Flow timeout exceeded."))
    outbox.append_event("flow_execution.timed_out", "flow_execution", flow_execution.id, {"flow_execution_id": flow_execution.id})
    return saved


def _positive_int(value: Any) -> int | None:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None
    return candidate if candidate > 0 else None


def _context(flow_execution: FlowExecutionDTO, nodes: list[FlowNodeDTO], executions: list[FlowNodeExecutionDTO]) -> dict[str, Any]:
    by_id = {node.id: node for node in nodes}
    return {
        "flow": {"input": flow_execution.input, "metadata": {"flow_execution_id": flow_execution.id, "execution_id": flow_execution.execution_id}},
        "nodes": {
            by_id[item.flow_node_id].key: {"status": item.status, "output": item.output, "input": item.input}
            for item in executions
            if item.flow_node_id in by_id
        },
    }


def _details(flow_execution: FlowExecutionDTO, execution: ExecutionDTO | None, version: FlowVersionDTO | None, nodes: list[FlowNodeDTO], edges: list[FlowEdgeDTO], node_executions: FlowNodeExecutionRepository) -> FlowExecutionDetailsDTO:
    return FlowExecutionDetailsDTO(flow_execution=flow_execution, execution=execution.__dict__ if execution else None, flow_version=version, nodes=nodes, edges=edges, node_executions=node_executions.list_for_flow_execution(flow_execution.id))


def _node_status_from_task(status: str) -> str:
    if status == "succeeded":
        return "succeeded"
    if status == "timed_out":
        return "timed_out"
    if status == "cancelled":
        return "cancelled"
    if status == "skipped":
        return "skipped"
    return "failed"


def _node_from_payload(flow_version_id: str, payload: dict[str, Any]) -> FlowNodeDTO:
    return FlowNodeDTO(
        id=new_id("fln"),
        flow_version_id=flow_version_id,
        key=str(payload["key"]),
        name=str(payload.get("name") or payload["key"]),
        node_type=str(payload.get("node_type") or "automation"),
        automation_version_id=payload.get("automation_version_id"),
        configuration=payload.get("configuration") or {},
        input_mapping=payload.get("input_mapping") or {},
        output_mapping=payload.get("output_mapping") or {},
        condition=payload.get("condition"),
        retry_policy=payload.get("retry_policy") or {},
        timeout_policy=payload.get("timeout_policy") or {},
        failure_policy=str(payload.get("failure_policy") or "fail_flow"),
        execution_policy=payload.get("execution_policy") or {},
        position_metadata=payload.get("position_metadata") or {},
        created_at=utcnow(),
    )


def _requirements_snapshot(version, execution_id: str, priority: int, node: FlowNodeDTO) -> dict[str, Any]:
    return {
        "automation_version_id": version.automation_version_id,
        "runtime_version_id": version.runtime_version_id,
        "package_id": version.package_id,
        "execution_id": execution_id,
        "execution_mode": version.execution_mode,
        "required_capabilities": version.required_capabilities,
        "resource_requirements": version.resources,
        "exclusive_resources": version.exclusive_resources,
        "timeout_policy": node.timeout_policy or version.timeout_policy,
        "retry_policy": node.retry_policy or version.retry_policy,
        "priority": priority,
        "runtime": {"id": version.runtime_id, "version": version.runtime_version},
        "package": {"id": version.package_id, "sha256": version.package_sha256, "size_bytes": version.package_size_bytes},
        "required_pools": version.required_pools,
        "flow_node_id": node.id,
    }


def _execution_to_dto(execution: Execution) -> ExecutionDTO:
    return ExecutionDTO(id=execution.id, type=execution.type.value, origin=execution.origin.value, status=execution.status.value, requested_by=execution.requested_by, organization_id=execution.organization_id, input=execution.input, result=execution.result, correlation_id=execution.correlation_id, idempotency_key=execution.idempotency_key, created_at=execution.created_at, started_at=execution.started_at, completed_at=execution.completed_at, failure_summary=execution.failure_summary)


def _task_to_dto(task: TaskExecution) -> TaskExecutionDTO:
    return TaskExecutionDTO(id=task.id, execution_id=task.execution_id, automation_version_id=task.automation_version_id, status=task.status.value, priority=task.priority, parameters=task.parameters, input=task.input, result=task.result, retry_policy=task.retry_policy, timeout_policy=task.timeout_policy, created_at=task.created_at, ready_at=task.ready_at, queued_at=task.queued_at, started_at=task.started_at, completed_at=task.completed_at, current_attempt_number=task.current_attempt_number, failure_summary=task.failure_summary, requirements_snapshot=task.requirements_snapshot or {}, available_at=task.available_at, scheduling_attempts=task.scheduling_attempts, last_scheduling_attempt_at=task.last_scheduling_attempt_at, next_scheduling_attempt_at=task.next_scheduling_attempt_at, last_scheduling_failure=task.last_scheduling_failure)


def _require_flow(flows: FlowRepository, flow_id: str) -> FlowDTO:
    flow = flows.get(flow_id)
    if flow is None:
        raise ValueError("Flow not found.")
    return flow


def _require_version(versions: FlowVersionRepository, flow_version_id: str) -> FlowVersionDTO:
    version = versions.get(flow_version_id)
    if version is None:
        raise ValueError("FlowVersion not found.")
    return version


def _require_node(nodes: FlowNodeRepository, node_id: str) -> FlowNodeDTO:
    node = nodes.get(node_id)
    if node is None:
        raise ValueError("FlowNode not found.")
    return node


def _require_flow_execution(flow_executions: FlowExecutionRepository, flow_execution_id: str) -> FlowExecutionDTO:
    execution = flow_executions.get(flow_execution_id)
    if execution is None:
        raise ValueError("FlowExecution not found.")
    return execution


def _ensure_version_mutable(version: FlowVersionDTO) -> None:
    if version.status != "draft":
        raise ValueError("Published, deprecated or blocked FlowVersion is immutable.")


def _audit(audit_repo, actor: ActorDTO, action: str, resource_type: str, resource_id: str, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None) -> None:
    if audit_repo is None:
        return
    audit_repo.append(AuditEvent(id=new_id("aud"), actor_type=actor.actor_type, actor_id=actor.actor_id, action=action, resource_type=resource_type, resource_id=resource_id, before=before, after=after, ip=actor.ip, user_agent=actor.user_agent, occurred_at=utcnow()))


def utcnow() -> datetime:
    return datetime.utcnow()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
