from __future__ import annotations

from datetime import datetime

from gateway.agent_gateway.message_router import _complete_cancellation_request
from modules.dispatch.application.dto import CancellationRequestDTO


def test_complete_cancellation_request_marks_current_request_completed() -> None:
    request = CancellationRequestDTO(
        id="can_1",
        execution_id="exe_1",
        task_execution_id="task_1",
        execution_attempt_id="att_1",
        status="command_sent",
        requested_by="user_1",
        reason="stop",
        requested_at=datetime(2026, 8, 14),
    )
    repo = _CancellationRequests(request)
    adapters = _DispatchAdapters(repo)

    _complete_cancellation_request(adapters, "exe_1")

    assert repo.execution_id == "exe_1"
    assert repo.saved is not None
    assert repo.saved.status == "completed"
    assert repo.saved.completed_at is not None


def test_complete_cancellation_request_ignores_missing_request() -> None:
    repo = _CancellationRequests(None)
    adapters = _DispatchAdapters(repo)

    _complete_cancellation_request(adapters, "exe_1")

    assert repo.saved is None


class _DispatchAdapters:
    def __init__(self, cancellation_requests: "_CancellationRequests") -> None:
        self.cancellation_requests = cancellation_requests


class _CancellationRequests:
    def __init__(self, request: CancellationRequestDTO | None) -> None:
        self.request = request
        self.execution_id: str | None = None
        self.saved: CancellationRequestDTO | None = None

    def current_for_execution(self, execution_id: str) -> CancellationRequestDTO | None:
        self.execution_id = execution_id
        return self.request

    def save(self, request: CancellationRequestDTO) -> CancellationRequestDTO:
        self.saved = request
        return request
