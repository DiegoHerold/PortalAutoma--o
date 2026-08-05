from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import websockets
from sqlalchemy import select

from infrastructure.database import SessionLocal
from modules.dispatch.infrastructure.orm.models import ExecutionLeaseRecord
from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord, OrchestrationExecutionRecord, TaskExecutionRecord
from modules.orchestration.tests.smoke_execution_dispatch_flow import (
    BASE_URL,
    WS_URL,
    envelope,
    prepare_published_automation_version,
    recv_type,
)
from modules.telemetry.tests.smoke_telemetry_completion_artifacts import (
    _connect_smoke_agent,
    _now,
    _ready_running_attempt,
)


def _active_lease_for_attempt(attempt_id: str) -> ExecutionLeaseRecord | None:
    with SessionLocal() as db:
        return db.scalar(
            select(ExecutionLeaseRecord)
            .where(ExecutionLeaseRecord.execution_attempt_id == attempt_id, ExecutionLeaseRecord.status.in_(["active", "suspect"]))
            .order_by(ExecutionLeaseRecord.issued_at.desc())
            .limit(1)
        )


def _force_cancel_requested(execution_id: str, attempt_id: str) -> None:
    now = datetime.utcnow()
    with SessionLocal() as db:
        attempt = db.get(ExecutionAttemptRecord, attempt_id)
        assert attempt is not None
        task = db.get(TaskExecutionRecord, attempt.task_execution_id)
        assert task is not None
        execution = db.get(OrchestrationExecutionRecord, execution_id)
        assert execution is not None
        attempt.status = "cancel_requested"
        attempt.error_code = "CANCEL_REQUESTED"
        attempt.error_message = "sync smoke cancellation requested"
        task.status = "cancelling"
        task.started_at = task.started_at or now
        execution.status = "cancelling"
        execution.started_at = execution.started_at or now
        db.add_all([attempt, task, execution])
        db.commit()


async def _send_sync_state(ws, agent_id: str, agent_instance_id: str, payload: dict) -> dict:
    await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "agent.sync_state", payload)))
    ack = await recv_type(ws, "portal.ack")
    result = ack["payload"]["result"]
    assert result["agent_id"] == agent_id
    assert result["agent_instance_id"] == agent_instance_id
    return result


async def _send_terminal(ws, agent_id: str, agent_instance_id: str, message_type: str, attempt_id: str, sequence: int = 99) -> None:
    timestamp_field = {
        "execution.completed": "completed_at",
        "execution.cancelled": "cancelled_at",
        "execution.failed": "failed_at",
        "execution.timed_out": "timed_out_at",
    }[message_type]
    payload = {
        "execution_attempt_id": attempt_id,
        "event_id": f"evt_{uuid4().hex}",
        "event_sequence": sequence,
        "occurred_at": _now(),
        timestamp_field: _now(),
        "output": {"cleanup": True},
        "result": {"status": "cleanup"},
        "exit_code": 0,
        "code": "SMOKE_SYNC_CLEANUP",
        "message": "sync smoke cleanup",
    }
    await ws.send(json.dumps(envelope(agent_id, agent_instance_id, message_type, payload)))
    await recv_type(ws, "portal.ack")


async def _assert_in_sync(ws, agent_id: str, agent_instance_id: str, execution: dict, offer: dict) -> None:
    execution_id = execution["execution"]["id"]
    attempt_id = offer["execution_attempt_id"]
    lease = _active_lease_for_attempt(attempt_id)
    payload = {
        "agent_id": agent_id,
        "instance_id": agent_instance_id,
        "agent_state": "Ready",
        "reason": "smoke-in-sync",
        "sent_at": _now(),
        "running_executions": [
            {
                "execution_id": execution_id,
                "execution_attempt_id": attempt_id,
                "state": "Running",
                "workspace_path": "C:/smoke/workspace",
            }
        ],
        "reservations": [],
        "leases": [
            {
                "lease_id": lease.id,
                "execution_id": execution_id,
                "execution_attempt_id": attempt_id,
                "state": "Active",
                "expires_at": lease.expires_at.isoformat(),
            }
        ]
        if lease
        else [],
        "interactive_sessions": [],
        "outbox_summary": {"pending": 0},
        "inbox_summary": {"pending": 0},
        "pending_artifacts": [],
    }
    result = await _send_sync_state(ws, agent_id, agent_instance_id, payload)
    assert result["summary"]["IN_SYNC"] == 1
    assert result["leases"]["reported"] == (1 if lease else 0)
    assert not result["actions"]
    await _send_terminal(ws, agent_id, agent_instance_id, "execution.completed", attempt_id)


async def _assert_local_ahead(
    ws,
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    version_id: int,
    agent_id: str,
    agent_instance_id: str,
    capability_key: str,
) -> None:
    execution, offer = await _ready_running_attempt(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
    execution_id = execution["execution"]["id"]
    attempt_id = offer["execution_attempt_id"]
    result = await _send_sync_state(
        ws,
        agent_id,
        agent_instance_id,
        {
            "agent_id": agent_id,
            "instance_id": agent_instance_id,
            "agent_state": "Ready",
            "reason": "smoke-local-ahead",
            "sent_at": _now(),
            "running_executions": [
                {
                    "execution_id": execution_id,
                    "execution_attempt_id": attempt_id,
                    "state": "Succeeded",
                    "completed_at": _now(),
                    "output": {"ok": True, "source": "sync-smoke"},
                    "result": {"status": "ok"},
                    "exit_code": 0,
                }
            ],
            "reservations": [],
            "leases": [],
            "pending_artifacts": [],
        },
    )
    assert result["summary"]["LOCAL_AHEAD"] == 1
    assert result["decisions"][0]["applied_status"] == "succeeded"

    details_response = await client.get(f"/executions/{execution_id}", headers=admin_headers)
    details_response.raise_for_status()
    details = details_response.json()
    assert details["execution"]["status"] == "succeeded"
    assert details["current_attempt"]["status"] == "succeeded"


async def _assert_remote_ahead(
    ws,
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    version_id: int,
    agent_id: str,
    agent_instance_id: str,
    capability_key: str,
) -> None:
    execution, offer = await _ready_running_attempt(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
    execution_id = execution["execution"]["id"]
    attempt_id = offer["execution_attempt_id"]
    _force_cancel_requested(execution_id, attempt_id)
    result = await _send_sync_state(
        ws,
        agent_id,
        agent_instance_id,
        {
            "agent_id": agent_id,
            "instance_id": agent_instance_id,
            "agent_state": "Ready",
            "reason": "smoke-remote-ahead",
            "sent_at": _now(),
            "running_executions": [{"execution_id": execution_id, "execution_attempt_id": attempt_id, "state": "Running"}],
            "reservations": [],
            "leases": [],
            "pending_artifacts": [],
        },
    )
    assert result["summary"]["REMOTE_AHEAD"] == 1
    assert result["actions"][0]["type"] == "cancel"
    assert result["actions"][0]["execution_attempt_id"] == attempt_id
    await _send_terminal(ws, agent_id, agent_instance_id, "execution.cancelled", attempt_id)


async def _assert_conflict(
    ws,
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    version_id: int,
    agent_id: str,
    agent_instance_id: str,
    capability_key: str,
) -> None:
    execution, offer = await _ready_running_attempt(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
    execution_id = execution["execution"]["id"]
    attempt_id = offer["execution_attempt_id"]
    terminal_payload = {
        "execution_attempt_id": attempt_id,
        "event_id": f"evt_{uuid4().hex}",
        "event_sequence": 1,
        "occurred_at": _now(),
        "completed_at": _now(),
        "output": {"ok": True},
        "result": {"status": "ok"},
        "exit_code": 0,
    }
    await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "execution.completed", terminal_payload)))
    assert (await recv_type(ws, "portal.ack"))["payload"]["result"]["execution"]["execution"]["status"] == "succeeded"

    result = await _send_sync_state(
        ws,
        agent_id,
        agent_instance_id,
        {
            "agent_id": agent_id,
            "instance_id": agent_instance_id,
            "agent_state": "Ready",
            "reason": "smoke-conflict",
            "sent_at": _now(),
            "running_executions": [{"execution_id": execution_id, "execution_attempt_id": attempt_id, "state": "Running"}],
            "reservations": [],
            "leases": [],
            "pending_artifacts": [],
        },
    )
    assert result["summary"]["CONFLICT"] == 1
    assert result["decisions"][0]["reason"] == "PORTAL_TERMINAL_AGENT_ACTIVE"


async def main() -> None:
    version_id, _automation_id, capability_key = prepare_published_automation_version()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        login = await client.post("/auth/login", json={"email": "admin@portal.local", "password": "admin123"})
        login.raise_for_status()
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        agent_id, bearer, agent_instance_id = await _connect_smoke_agent(client, admin_headers)

        async with websockets.connect(WS_URL, additional_headers={"Authorization": f"Bearer {bearer}"}) as ws:
            await ws.send(
                json.dumps(
                    {
                        "message_type": "agent.connect",
                        "payload": {
                            "agent_id": agent_id,
                            "agent_instance_id": agent_instance_id,
                            "agent_version": "1.0.0",
                            "supported_protocol_versions": ["1.0"],
                        },
                    }
                )
            )
            assert (await recv_type(ws, "agent.connected"))["payload"]["selected_protocol_version"] == "1.0"

            execution, offer = await _ready_running_attempt(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
            await _assert_in_sync(ws, agent_id, agent_instance_id, execution, offer)
            await _assert_local_ahead(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
            await _assert_remote_ahead(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)
            await _assert_conflict(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)

        await client.post(f"/agents/{agent_id}/disable", headers=admin_headers, json={"reason": "sync state smoke complete"})

    print("sync state smoke ok")


if __name__ == "__main__":
    asyncio.run(main())
