from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.orchestration.flows.application.dto import (
    FlowDTO,
    FlowEdgeDTO,
    FlowExecutionDTO,
    FlowNodeDTO,
    FlowNodeExecutionDTO,
    FlowVersionDTO,
)
from modules.orchestration.flows.infrastructure.orm.models import (
    FlowEdgeRecord,
    FlowExecutionRecord,
    FlowNodeExecutionRecord,
    FlowNodeRecord,
    FlowRecord,
    FlowVersionRecord,
)


class SqlAlchemyFlowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, flow: FlowDTO) -> FlowDTO:
        row = FlowRecord(**_dict(flow))
        self.db.add(row)
        self.db.flush()
        return _flow_to_dto(row)

    def save(self, flow: FlowDTO) -> FlowDTO:
        row = self.db.get(FlowRecord, flow.id)
        if row is None:
            return self.add(flow)
        for key, value in _dict(flow).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _flow_to_dto(row)

    def get(self, flow_id: str) -> FlowDTO | None:
        row = self.db.get(FlowRecord, flow_id)
        return _flow_to_dto(row) if row else None

    def get_by_key(self, key: str) -> FlowDTO | None:
        row = self.db.scalar(select(FlowRecord).where(FlowRecord.key == key))
        return _flow_to_dto(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> list[FlowDTO]:
        rows = self.db.scalars(select(FlowRecord).order_by(FlowRecord.created_at.desc()).offset(offset).limit(limit)).all()
        return [_flow_to_dto(row) for row in rows]


class SqlAlchemyFlowVersionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, version: FlowVersionDTO) -> FlowVersionDTO:
        row = FlowVersionRecord(**_dict(version))
        self.db.add(row)
        self.db.flush()
        return _version_to_dto(row)

    def save(self, version: FlowVersionDTO) -> FlowVersionDTO:
        row = self.db.get(FlowVersionRecord, version.id)
        if row is None:
            return self.add(version)
        for key, value in _dict(version).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _version_to_dto(row)

    def get(self, flow_version_id: str) -> FlowVersionDTO | None:
        row = self.db.get(FlowVersionRecord, flow_version_id)
        return _version_to_dto(row) if row else None

    def list_for_flow(self, flow_id: str) -> list[FlowVersionDTO]:
        rows = self.db.scalars(select(FlowVersionRecord).where(FlowVersionRecord.flow_id == flow_id).order_by(FlowVersionRecord.created_at.desc())).all()
        return [_version_to_dto(row) for row in rows]


class SqlAlchemyFlowNodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, node: FlowNodeDTO) -> FlowNodeDTO:
        row = FlowNodeRecord(**_dict(node))
        self.db.add(row)
        self.db.flush()
        return _node_to_dto(row)

    def save(self, node: FlowNodeDTO) -> FlowNodeDTO:
        row = self.db.get(FlowNodeRecord, node.id)
        if row is None:
            return self.add(node)
        for key, value in _dict(node).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _node_to_dto(row)

    def get(self, node_id: str) -> FlowNodeDTO | None:
        row = self.db.get(FlowNodeRecord, node_id)
        return _node_to_dto(row) if row else None

    def list_for_version(self, flow_version_id: str) -> list[FlowNodeDTO]:
        rows = self.db.scalars(select(FlowNodeRecord).where(FlowNodeRecord.flow_version_id == flow_version_id).order_by(FlowNodeRecord.created_at, FlowNodeRecord.key)).all()
        return [_node_to_dto(row) for row in rows]

    def remove(self, node_id: str) -> None:
        row = self.db.get(FlowNodeRecord, node_id)
        if row is not None:
            self.db.delete(row)
            self.db.flush()


class SqlAlchemyFlowEdgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, edge: FlowEdgeDTO) -> FlowEdgeDTO:
        row = FlowEdgeRecord(**_dict(edge))
        self.db.add(row)
        self.db.flush()
        return _edge_to_dto(row)

    def get(self, edge_id: str) -> FlowEdgeDTO | None:
        row = self.db.get(FlowEdgeRecord, edge_id)
        return _edge_to_dto(row) if row else None

    def list_for_version(self, flow_version_id: str) -> list[FlowEdgeDTO]:
        rows = self.db.scalars(select(FlowEdgeRecord).where(FlowEdgeRecord.flow_version_id == flow_version_id).order_by(FlowEdgeRecord.created_at, FlowEdgeRecord.id)).all()
        return [_edge_to_dto(row) for row in rows]

    def remove(self, edge_id: str) -> None:
        row = self.db.get(FlowEdgeRecord, edge_id)
        if row is not None:
            self.db.delete(row)
            self.db.flush()


class SqlAlchemyFlowExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, execution: FlowExecutionDTO) -> FlowExecutionDTO:
        row = FlowExecutionRecord(**_dict(execution))
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def save(self, execution: FlowExecutionDTO) -> FlowExecutionDTO:
        row = self.db.get(FlowExecutionRecord, execution.id)
        if row is None:
            return self.add(execution)
        for key, value in _dict(execution).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def get(self, flow_execution_id: str) -> FlowExecutionDTO | None:
        row = self.db.get(FlowExecutionRecord, flow_execution_id)
        return _execution_to_dto(row) if row else None

    def get_by_execution_id(self, execution_id: str) -> FlowExecutionDTO | None:
        row = self.db.scalar(select(FlowExecutionRecord).where(FlowExecutionRecord.execution_id == execution_id))
        return _execution_to_dto(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> list[FlowExecutionDTO]:
        rows = self.db.scalars(select(FlowExecutionRecord).order_by(FlowExecutionRecord.created_at.desc()).offset(offset).limit(limit)).all()
        return [_execution_to_dto(row) for row in rows]

    def active_for_schedule(self, schedule_id: str) -> list[FlowExecutionDTO]:
        rows = self.db.scalars(
            select(FlowExecutionRecord).where(
                FlowExecutionRecord.schedule_execution_id == schedule_id,
                FlowExecutionRecord.status.in_(["created", "pending", "running", "cancelling"]),
            )
        ).all()
        return [_execution_to_dto(row) for row in rows]


class SqlAlchemyFlowNodeExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, execution: FlowNodeExecutionDTO) -> FlowNodeExecutionDTO:
        row = FlowNodeExecutionRecord(**_dict(execution))
        self.db.add(row)
        self.db.flush()
        return _node_execution_to_dto(row)

    def save(self, execution: FlowNodeExecutionDTO) -> FlowNodeExecutionDTO:
        row = self.db.get(FlowNodeExecutionRecord, execution.id)
        if row is None:
            return self.add(execution)
        for key, value in _dict(execution).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _node_execution_to_dto(row)

    def get(self, flow_node_execution_id: str) -> FlowNodeExecutionDTO | None:
        row = self.db.get(FlowNodeExecutionRecord, flow_node_execution_id)
        return _node_execution_to_dto(row) if row else None

    def get_by_task_execution_id(self, task_execution_id: str) -> FlowNodeExecutionDTO | None:
        row = self.db.scalar(select(FlowNodeExecutionRecord).where(FlowNodeExecutionRecord.task_execution_id == task_execution_id))
        return _node_execution_to_dto(row) if row else None

    def list_for_flow_execution(self, flow_execution_id: str) -> list[FlowNodeExecutionDTO]:
        rows = self.db.scalars(select(FlowNodeExecutionRecord).where(FlowNodeExecutionRecord.flow_execution_id == flow_execution_id).order_by(FlowNodeExecutionRecord.id)).all()
        return [_node_execution_to_dto(row) for row in rows]

    def list_active(self, limit: int = 100) -> list[FlowNodeExecutionDTO]:
        rows = self.db.scalars(
            select(FlowNodeExecutionRecord)
            .where(FlowNodeExecutionRecord.status.in_(["ready", "running"]))
            .order_by(FlowNodeExecutionRecord.id)
            .limit(limit)
        ).all()
        return [_node_execution_to_dto(row) for row in rows]


def _dict(dto) -> dict[str, Any]:
    return dto.__dict__.copy()


def _flow_to_dto(row: FlowRecord) -> FlowDTO:
    return FlowDTO(id=row.id, key=row.key, name=row.name, description=row.description, category_id=row.category_id, tags=row.tags or [], status=row.status, created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at)


def _version_to_dto(row: FlowVersionRecord) -> FlowVersionDTO:
    return FlowVersionDTO(id=row.id, flow_id=row.flow_id, version=row.version, status=row.status, definition=row.definition or {}, input_schema=row.input_schema, output_schema=row.output_schema, release_notes=row.release_notes, created_by=row.created_by, created_at=row.created_at, published_by=row.published_by, published_at=row.published_at, deprecated_at=row.deprecated_at, blocked_at=row.blocked_at)


def _node_to_dto(row: FlowNodeRecord) -> FlowNodeDTO:
    return FlowNodeDTO(id=row.id, flow_version_id=row.flow_version_id, key=row.key, name=row.name, node_type=row.node_type, automation_version_id=row.automation_version_id, configuration=row.configuration or {}, input_mapping=row.input_mapping or {}, output_mapping=row.output_mapping or {}, condition=row.condition, retry_policy=row.retry_policy or {}, timeout_policy=row.timeout_policy or {}, failure_policy=row.failure_policy, execution_policy=row.execution_policy or {}, position_metadata=row.position_metadata or {}, created_at=row.created_at)


def _edge_to_dto(row: FlowEdgeRecord) -> FlowEdgeDTO:
    return FlowEdgeDTO(id=row.id, flow_version_id=row.flow_version_id, source_node_id=row.source_node_id, target_node_id=row.target_node_id, edge_type=row.edge_type, condition=row.condition, mapping=row.mapping or {}, created_at=row.created_at)


def _execution_to_dto(row: FlowExecutionRecord) -> FlowExecutionDTO:
    return FlowExecutionDTO(id=row.id, execution_id=row.execution_id, flow_version_id=row.flow_version_id, status=row.status, origin=row.origin, input=row.input or {}, output=row.output, requested_by=row.requested_by, schedule_execution_id=row.schedule_execution_id, correlation_id=row.correlation_id, created_at=row.created_at, started_at=row.started_at, completed_at=row.completed_at, cancellation_requested_at=row.cancellation_requested_at, failure_summary=row.failure_summary)


def _node_execution_to_dto(row: FlowNodeExecutionRecord) -> FlowNodeExecutionDTO:
    return FlowNodeExecutionDTO(id=row.id, flow_execution_id=row.flow_execution_id, flow_node_id=row.flow_node_id, task_execution_id=row.task_execution_id, status=row.status, input=row.input or {}, output=row.output, condition_result=row.condition_result, dependency_state=row.dependency_state or {}, started_at=row.started_at, completed_at=row.completed_at, skipped_at=row.skipped_at, failure_summary=row.failure_summary, revision=row.revision)
