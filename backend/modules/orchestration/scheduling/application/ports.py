from __future__ import annotations

from datetime import datetime
from typing import Protocol

from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.scheduling.application.dto import ScheduleDTO, ScheduleExecutionDTO


class TransactionManager(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class ScheduleRepository(Protocol):
    def add(self, schedule: ScheduleDTO) -> ScheduleDTO:
        raise NotImplementedError

    def save(self, schedule: ScheduleDTO) -> ScheduleDTO:
        raise NotImplementedError

    def get(self, schedule_id: int) -> ScheduleDTO | None:
        raise NotImplementedError

    def get_by_key(self, key: str) -> ScheduleDTO | None:
        raise NotImplementedError

    def list(self, limit: int = 100, offset: int = 0) -> list[ScheduleDTO]:
        raise NotImplementedError

    def due(self, now: datetime, limit: int = 100) -> list[ScheduleDTO]:
        raise NotImplementedError


class ScheduleExecutionRepository(Protocol):
    def add(self, execution: ScheduleExecutionDTO) -> ScheduleExecutionDTO:
        raise NotImplementedError

    def save(self, execution: ScheduleExecutionDTO) -> ScheduleExecutionDTO:
        raise NotImplementedError

    def get(self, schedule_execution_id: str) -> ScheduleExecutionDTO | None:
        raise NotImplementedError

    def get_by_schedule_time(self, schedule_id: int, scheduled_for: datetime) -> ScheduleExecutionDTO | None:
        raise NotImplementedError

    def list_for_schedule(self, schedule_id: int) -> list[ScheduleExecutionDTO]:
        raise NotImplementedError

    def active_for_schedule(self, schedule_id: int) -> list[ScheduleExecutionDTO]:
        raise NotImplementedError

    def list_active(self, limit: int = 100) -> list[ScheduleExecutionDTO]:
        raise NotImplementedError


class ScheduleExecutionCreator(Protocol):
    def create_execution(self, schedule: ScheduleDTO, schedule_execution: ScheduleExecutionDTO, actor: ActorDTO) -> dict:
        raise NotImplementedError


class OutboxPort(Protocol):
    def append_event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict, correlation_id: str | None = None, causation_id: str | None = None) -> None:
        raise NotImplementedError
