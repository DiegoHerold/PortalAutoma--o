from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import websockets

from modules.orchestration.tests.smoke_execution_dispatch_flow import (
    BASE_URL,
    WS_URL,
    advertise_capability,
    create_execution,
    envelope,
    prepare_published_automation_version,
    recv_type,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _connect_smoke_agent(client: httpx.AsyncClient, admin_headers: dict[str, str]):
    token_response = await client.post("/agents/registration-tokens", headers=admin_headers, json={"expires_in_seconds": 600})
    token_response.raise_for_status()
    registration_token = token_response.json()["registration_token"]

    local_identity = f"telemetry-smoke-{uuid4().hex}"
    register_response = await client.post(
        "/agents/register",
        json={
            "registration_token": registration_token,
            "local_identity": local_identity,
            "hostname": "telemetry-smoke-agent",
            "name": "Telemetry Smoke Agent",
            "machine_fingerprint": local_identity,
            "agent_version": "1.0.0",
        },
    )
    register_response.raise_for_status()
    registered = register_response.json()
    return registered["agent"]["id"], registered["credential"]["bearer_token"], f"agi_tel_smoke_{uuid4().hex}"


async def _ready_running_attempt(
    ws,
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    version_id: int,
    agent_id: str,
    agent_instance_id: str,
    capability_key: str,
) -> tuple[dict, dict]:
    await ws.send(
        json.dumps(
            envelope(
                agent_id,
                agent_instance_id,
                "agent.heartbeat",
                {
                    "observed_at": _now(),
                    "agent_version": "1.0.0",
                    "health": "healthy",
                    "resources": {
                        "cpu_percentage": 8,
                        "memory_total_mb": 4096,
                        "memory_available_mb": 3000,
                        "memory_percentage": 27,
                        "disk_free_mb": 100000,
                    },
                    "pools": {
                        "interactive": {"total": 1, "used": 0, "reserved": 0},
                        "background": {"total": 2, "used": 0, "reserved": 0},
                        "browser": {"total": 1, "used": 0, "reserved": 0},
                    },
                },
            )
        )
    )
    assert (await recv_type(ws, "portal.ack"))["payload"]["result"]["ok"] is True
    await advertise_capability(ws, agent_id, agent_instance_id, capability_key)

    execution = await create_execution(client, admin_headers, version_id, agent_id)
    offer_message = await recv_type(ws, "execution.offer")
    offer = offer_message["payload"]
    await ws.send(
        json.dumps(
            envelope(
                agent_id,
                agent_instance_id,
                "execution.accepted",
                {
                    "execution_offer_id": offer["execution_offer_id"],
                    "execution_attempt_id": offer["execution_attempt_id"],
                    "agent_id": agent_id,
                    "agent_instance_id": agent_instance_id,
                    "accepted_at": _now(),
                },
                correlation_id=offer_message["message_id"],
            )
        )
    )
    assert (await recv_type(ws, "portal.ack"))["payload"]["result"]["commit_command_id"]
    commit_message = await recv_type(ws, "execution.commit")
    commit = commit_message["payload"]
    await ws.send(
        json.dumps(
            envelope(
                agent_id,
                agent_instance_id,
                "agent.command.ack",
                {
                    "command_id": commit["command_id"],
                    "command_sequence": commit["command_sequence"],
                    "status": "received",
                },
                correlation_id=commit_message["message_id"],
            )
        )
    )
    assert (await recv_type(ws, "portal.ack"))["payload"]["result"]["ok"] is True

    await ws.send(
        json.dumps(
            envelope(
                agent_id,
                agent_instance_id,
                "execution.started",
                {
                    "execution_offer_id": offer["execution_offer_id"],
                    "execution_attempt_id": offer["execution_attempt_id"],
                    "agent_id": agent_id,
                    "agent_instance_id": agent_instance_id,
                    "started_at": _now(),
                },
            )
        )
    )
    assert (await recv_type(ws, "portal.ack"))["payload"]["result"]["status"] == "running"
    return execution, offer


async def _send_batch(ws, agent_id: str, agent_instance_id: str, attempt_id: str, events: list[dict]) -> dict:
    await ws.send(
        json.dumps(
            envelope(
                agent_id,
                agent_instance_id,
                "execution.event.batch",
                {"execution_attempt_id": attempt_id, "events": events},
            )
        )
    )
    ack = await recv_type(ws, "portal.ack")
    assert ack["payload"]["result"]["message_type"] == "execution.event.ack"
    return ack["payload"]["result"]


async def _read_first_execution_event_from_sse(client: httpx.AsyncClient, execution_id: str, token: str, last_event_id: str) -> dict:
    headers = {"Last-Event-ID": last_event_id}
    async with client.stream("GET", f"/executions/{execution_id}/stream?token={token}", headers=headers, timeout=20) as response:
        response.raise_for_status()
        current: dict[str, str] = {}
        async for line in response.aiter_lines():
            if line == "":
                if current.get("event") == "execution.event":
                    return json.loads(current["data"])
                current = {}
                continue
            if line.startswith(":"):
                continue
            key, _, value = line.partition(":")
            current[key] = value.lstrip()
    raise AssertionError("SSE stream did not yield an execution.event.")


async def _assert_failed_terminal(
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
    failed_payload = {
        "execution_attempt_id": attempt_id,
        "event_id": f"evt_{uuid4().hex}",
        "event_sequence": 1,
        "occurred_at": _now(),
        "failed_at": _now(),
        "error_code": "SMOKE_FAILED",
        "error_message": "Smoke failure terminal",
        "exit_code": 99,
    }
    await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "execution.failed", failed_payload)))
    failed_ack = await recv_type(ws, "portal.ack")
    assert failed_ack["payload"]["result"]["execution"]["execution"]["status"] == "failed"

    await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "execution.failed", failed_payload)))
    duplicate_failed_ack = await recv_type(ws, "portal.ack")
    assert duplicate_failed_ack["payload"]["result"]["execution"]["execution"]["status"] == "failed"

    details_response = await client.get(f"/executions/{execution_id}", headers=admin_headers)
    details_response.raise_for_status()
    details = details_response.json()
    assert details["execution"]["status"] == "failed"
    assert details["tasks"][0]["status"] == "failed"
    assert details["current_attempt"]["status"] == "failed"
    assert details["current_attempt"]["error_code"] == "SMOKE_FAILED"


async def main() -> None:
    version_id, _automation_id, capability_key = prepare_published_automation_version()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        login = await client.post("/auth/login", json={"email": "admin@portal.local", "password": "admin123"})
        login.raise_for_status()
        access_token = login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {access_token}"}
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
            execution_id = execution["execution"]["id"]
            attempt_id = offer["execution_attempt_id"]

            first_ack = await _send_batch(
                ws,
                agent_id,
                agent_instance_id,
                attempt_id,
                [
                    {
                        "event_id": f"evt_{uuid4().hex}",
                        "event_sequence": 1,
                        "event_type": "log",
                        "occurred_at": _now(),
                        "level": "INFO",
                        "payload": {"message": "Smoke log", "password": "must-mask"},
                    },
                    {
                        "event_id": f"evt_{uuid4().hex}",
                        "event_sequence": 3,
                        "event_type": "task.progress",
                        "occurred_at": _now(),
                        "payload": {"percentage": 40, "message": "40%"},
                    },
                ],
            )
            assert first_ack["accepted_events"] == 2
            assert first_ack["acknowledgement"]["highest_received_sequence"] == 3
            assert first_ack["acknowledgement"]["highest_contiguous_sequence"] == 1
            assert first_ack["acknowledgement"]["missing_ranges"] == [{"from": 2, "to": 2}]

            duplicate_ack = await _send_batch(
                ws,
                agent_id,
                agent_instance_id,
                attempt_id,
                [
                    {
                        "event_id": f"evt_duplicate_{uuid4().hex}",
                        "event_sequence": 1,
                        "event_type": "log",
                        "occurred_at": _now(),
                        "level": "INFO",
                        "payload": {"message": "Duplicate should not persist"},
                    }
                ],
            )
            assert duplicate_ack["accepted_events"] == 0
            assert duplicate_ack["duplicate_events"] == 1

            second_event_id = f"evt_{uuid4().hex}"
            contiguous_ack = await _send_batch(
                ws,
                agent_id,
                agent_instance_id,
                attempt_id,
                [
                    {
                        "event_id": second_event_id,
                        "event_sequence": 2,
                        "event_type": "metric",
                        "occurred_at": _now(),
                        "payload": {"metric_name": "rows_processed", "metric_type": "counter", "value": 12, "unit": "rows"},
                    }
                ],
            )
            assert contiguous_ack["acknowledgement"]["highest_contiguous_sequence"] == 3
            assert contiguous_ack["acknowledgement"]["missing_ranges"] == []

            logs_response = await client.get(f"/executions/{execution_id}/logs", headers=admin_headers)
            logs_response.raise_for_status()
            logs = logs_response.json()["items"]
            assert len(logs) == 1
            assert logs[0]["payload"]["password"] == "***"

            progress_response = await client.get(f"/executions/{execution_id}/progress", headers=admin_headers)
            progress_response.raise_for_status()
            assert progress_response.json()["percentage"] == 40

            metrics_response = await client.get(f"/executions/{execution_id}/metrics", headers=admin_headers)
            metrics_response.raise_for_status()
            metric_names = {metric["metric_name"] for metric in metrics_response.json()}
            assert {"rows_processed", "progress_percentage"}.issubset(metric_names)

            sse_payload = await _read_first_execution_event_from_sse(client, execution_id, access_token, logs[0]["id"])
            assert sse_payload["event"]["id"]

            artifact_bytes = b"hello artifact smoke"
            artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
            artifact_id = f"art_{uuid4().hex}"
            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "artifact.created",
                        {
                            "artifact_id": artifact_id,
                            "execution_attempt_id": attempt_id,
                            "name": "smoke.txt",
                            "content_type": "text/plain",
                            "size_bytes": len(artifact_bytes),
                            "sha256": artifact_sha,
                        },
                    )
                )
            )
            artifact_created = await recv_type(ws, "portal.ack")
            upload = artifact_created["payload"]["result"]
            assert upload["artifact"]["id"] == artifact_id
            assert upload["upload_url"]
            put_response = await client.put(upload["upload_url"], content=artifact_bytes, headers={"content-type": "text/plain"})
            put_response.raise_for_status()

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "artifact.uploaded",
                        {
                            "artifact_id": artifact_id,
                            "execution_attempt_id": attempt_id,
                            "upload_session_id": upload["upload_session_id"],
                            "size_bytes": len(artifact_bytes),
                            "sha256": artifact_sha,
                        },
                    )
                )
            )
            uploaded_ack = await recv_type(ws, "portal.ack")
            assert uploaded_ack["payload"]["result"]["status"] == "available"

            artifacts_response = await client.get(f"/executions/{execution_id}/artifacts", headers=admin_headers)
            artifacts_response.raise_for_status()
            assert artifacts_response.json()[0]["status"] == "available"

            download_response = await client.get(f"/artifacts/{artifact_id}/download", headers=admin_headers, follow_redirects=True)
            download_response.raise_for_status()
            assert download_response.content == artifact_bytes

            terminal_payload = {
                "execution_attempt_id": attempt_id,
                "event_id": f"evt_{uuid4().hex}",
                "event_sequence": 4,
                "occurred_at": _now(),
                "completed_at": _now(),
                "output": {"ok": True, "artifact_id": artifact_id},
                "result": {"status": "ok"},
                "exit_code": 0,
                "resource_usage": {"duration_ms": 123},
            }
            await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "execution.completed", terminal_payload)))
            completed_ack = await recv_type(ws, "portal.ack")
            assert completed_ack["payload"]["result"]["execution"]["execution"]["status"] == "succeeded"

            await ws.send(json.dumps(envelope(agent_id, agent_instance_id, "execution.completed", terminal_payload)))
            duplicate_terminal_ack = await recv_type(ws, "portal.ack")
            assert duplicate_terminal_ack["payload"]["result"]["execution"]["execution"]["status"] == "succeeded"

            details_response = await client.get(f"/executions/{execution_id}", headers=admin_headers)
            details_response.raise_for_status()
            details = details_response.json()
            assert details["execution"]["status"] == "succeeded"
            assert details["tasks"][0]["status"] == "succeeded"
            assert details["current_attempt"]["status"] == "succeeded"
            assert details["telemetry"]["event_count"] == 4
            assert details["telemetry"]["artifact_count"] == 1

            await _assert_failed_terminal(ws, client, admin_headers, version_id, agent_id, agent_instance_id, capability_key)

        await client.post(f"/agents/{agent_id}/disable", headers=admin_headers, json={"reason": "telemetry smoke complete"})

    print("telemetry completion artifacts smoke ok")


if __name__ == "__main__":
    asyncio.run(main())
