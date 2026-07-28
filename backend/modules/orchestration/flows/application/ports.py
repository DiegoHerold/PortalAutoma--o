from __future__ import annotations

from datetime import datetime
from typing import Protocol

from modules.orchestration.flows.application.dto import (
    FlowDTO,
    FlowEdgeDTO,
    FlowExecutionDTO,
    FlowNodeDTO,
    FlowNodeExecutionDTO,
    FlowVersionDTO,
)


class TransactionManager(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class FlowRepository(Protocol):
    def add(self, flow: FlowDTO) -> FlowDTO:
        raise NotImplementedError

    def save(self, flow: FlowDTO) -> FlowDTO:
        raise NotImplementedError

    def get(self, flow_id: str) -> FlowDTO | None:
        raise NotImplementedError

    def get_by_key(self, key: str) -> FlowDTO | None:
        raise NotImplementedError

    def list(self, limit: int = 100, offset: int = 0) -> list[FlowDTO]:
        raise NotImplementedError


class FlowVersionRepository(Protocol):
    def add(self, version: FlowVersionDTO) -> FlowVersionDTO:
        raise NotImplementedError

    def save(self, version: FlowVersionDTO) -> FlowVersionDTO:
        raise NotImplementedError

    def get(self, flow_version_id: str) -> FlowVersionDTO | None:
        raise NotImplementedError

    def list_for_flow(self, flow_id: str) -> list[FlowVersionDTO]:
        raise NotImplementedError


class FlowNodeRepository(Protocol):
    def add(self, node: FlowNodeDTO) -> FlowNodeDTO:
        raise NotImplementedError

    def save(self, node: FlowNodeDTO) -> FlowNodeDTO:
        raise NotImplementedError

    def get(self, node_id: str) -> FlowNodeDTO | None:
        raise NotImplementedError

    def list_for_version(self, flow_version_id: str) -> list[FlowNodeDTO]:
        raise NotImplementedError

    def remove(self, node_id: str) -> None:
        raise NotImplementedError


class FlowEdgeRepository(Protocol):
    def add(self, edge: FlowEdgeDTO) -> FlowEdgeDTO:
        raise NotImplementedError

    def get(self, edge_id: str) -> FlowEdgeDTO | None:
        raise NotImplementedError

    def list_for_version(self, flow_version_id: str) -> list[FlowEdgeDTO]:
        raise NotImplementedError

    def remove(self, edge_id: str) -> None:
        raise NotImplementedError


class FlowExecutionRepository(Protocol):
    def add(self, execution: FlowExecutionDTO) -> FlowExecutionDTO:
        raise NotImplementedError

    def save(self, execution: FlowExecutionDTO) -> FlowExecutionDTO:
        raise NotImplementedError

    def get(self, flow_execution_id: str) -> FlowExecutionDTO | None:
        raise NotImplementedError

    def get_by_execution_id(self, execution_id: str) -> FlowExecutionDTO | None:
        raise NotImplementedError

    def list(self, limit: int = 100, offset: int = 0) -> list[FlowExecutionDTO]:
        raise NotImplementedError

    def active_for_schedule(self, schedule_id: str) -> list[FlowExecutionDTO]:
        raise NotImplementedError


class FlowNodeExecutionRepository(Protocol):
    def add(self, execution: FlowNodeExecutionDTO) -> FlowNodeExecutionDTO:
        raise NotImplementedError

    def save(self, execution: FlowNodeExecutionDTO) -> FlowNodeExecutionDTO:
        raise NotImplementedError

    def get(self, flow_node_execution_id: str) -> FlowNodeExecutionDTO | None:
        raise NotImplementedError

    def get_by_task_execution_id(self, task_execution_id: str) -> FlowNodeExecutionDTO | None:
        raise NotImplementedError

    def list_for_flow_execution(self, flow_execution_id: str) -> list[FlowNodeExecutionDTO]:
        raise NotImplementedError

    def list_active(self, limit: int = 100) -> list[FlowNodeExecutionDTO]:
        raise NotImplementedError


class OutboxPort(Protocol):
    def append_event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict, correlation_id: str | None = None, causation_id: str | None = None) -> None:
        raise NotImplementedError


class Clock(Protocol):
    def now(self) -> datetime:
        raise NotImplementedError
