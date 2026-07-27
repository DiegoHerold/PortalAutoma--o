from __future__ import annotations

from datetime import datetime

import pytest

from modules.orchestration.domain.errors import InvalidExecutionTransition
from modules.orchestration.domain.execution import Execution
from modules.orchestration.domain.execution_attempt import ExecutionAttempt
from modules.orchestration.domain.states import ExecutionOrigin, ExecutionStatus, ExecutionType, TaskExecutionStatus
from modules.orchestration.domain.task_execution import TaskExecution


def test_execution_reaches_running_through_required_states() -> None:
    now = datetime.utcnow()
    execution = Execution.create(
        id="exe_1",
        origin=ExecutionOrigin.MANUAL,
        requested_by="1",
        organization_id=None,
        input={},
        correlation_id=None,
        idempotency_key=None,
        now=now,
    )

    assert execution.type == ExecutionType.AUTOMATION
    assert execution.status == ExecutionStatus.CREATED
    assert execution.mark_pending().mark_running(now).status == ExecutionStatus.RUNNING


def test_execution_rejects_invalid_transition() -> None:
    execution = Execution.create(
        id="exe_1",
        origin=ExecutionOrigin.MANUAL,
        requested_by=None,
        organization_id=None,
        input={},
        correlation_id=None,
        idempotency_key=None,
        now=datetime.utcnow(),
    )

    with pytest.raises(InvalidExecutionTransition):
        execution.mark_running(datetime.utcnow())


def test_task_execution_does_not_have_offer_state() -> None:
    now = datetime.utcnow()
    task = TaskExecution.create(
        id="task_1",
        execution_id="exe_1",
        automation_version_id=1,
        priority=0,
        parameters={},
        input={},
        timeout_seconds=60,
        now=now,
    )

    queued = task.mark_ready(now).mark_queued(now)

    assert queued.status == TaskExecutionStatus.QUEUED
    assert "offered" not in {item.value for item in TaskExecutionStatus}


def test_attempt_physical_lifecycle_until_running() -> None:
    now = datetime.utcnow()
    attempt = ExecutionAttempt.create(
        id="att_1",
        task_execution_id="task_1",
        attempt_number=1,
        agent_id="agt_1",
        agent_instance_id="agi_1",
        runtime_version_id="rtv_1",
        package_id="pkg_1",
        now=now,
    )

    running = attempt.mark_offered("off_1", now).mark_accepted(now).mark_committed(now).mark_running(now)

    assert running.status == "running"
    assert running.preparing_at is not None
    assert running.started_at is not None


def test_attempt_rejection_does_not_touch_task_or_execution_states() -> None:
    now = datetime.utcnow()
    attempt = ExecutionAttempt.create(
        id="att_1",
        task_execution_id="task_1",
        attempt_number=1,
        agent_id="agt_1",
        agent_instance_id="agi_1",
        runtime_version_id=None,
        package_id=None,
        now=now,
    )

    rejected = attempt.mark_offered("off_1", now).mark_rejected("AGENT_OVERLOADED", "busy", now)

    assert rejected.status == "rejected"
