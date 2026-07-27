from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import websockets
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.automation import Automation
from app.models.automation_version import AutomationVersion
from app.models.category import Category
from modules.catalog.infrastructure.orm.models import AutomationManifestRecord, AutomationPackageRecord, RuntimeRecord, RuntimeVersionRecord
from modules.storage.infrastructure.orm.models import StoredObjectRecord


BASE_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/api/v1/agent-gateway/connect"


def envelope(agent_id: str, agent_instance_id: str, message_type: str, payload: dict, correlation_id: str | None = None) -> dict:
    return {
        "protocol_version": "1.0",
        "message_id": f"msg_{uuid4().hex}",
        "message_type": message_type,
        "sent_at": datetime.now(UTC).isoformat(),
        "agent_id": agent_id,
        "agent_instance_id": agent_instance_id,
        "correlation_id": correlation_id,
        "causation_id": None,
        "payload": payload,
    }


def prepare_published_automation_version() -> tuple[int, int]:
    now = datetime.utcnow()
    marker = uuid4().hex[:12]
    runtime_key = "python-desktop"
    runtime_version = "3.13"
    package_sha = hashlib.sha256(marker.encode("utf-8")).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "automation": {
            "id": f"smoke.execution.{marker}",
            "name": f"Smoke Execution {marker}",
            "version": "1.0.0",
            "description": "Execution dispatch smoke automation.",
            "category": "smoke",
        },
        "runtime": {"id": runtime_key, "version": runtime_version},
        "entrypoint": {"type": "python-function", "module": "application.main", "function": "run"},
        "execution": {"mode": "background", "timeout_seconds": 300, "graceful_cancellation_seconds": 30},
        "resources": {"cpu_units": 1, "memory_mb": 256, "disk_mb": 100},
        "capabilities": {"required": []},
        "exclusive_resources": [],
        "schemas": {"input": None, "output": None},
    }
    with SessionLocal() as db:
        category = db.scalar(select(Category).where(Category.slug == "smoke"))
        if category is None:
            category = Category(name="Smoke", slug="smoke", description="Smoke tests", is_active=True)
            db.add(category)
            db.flush()

        runtime = db.scalar(select(RuntimeRecord).where(RuntimeRecord.key == runtime_key))
        if runtime is None:
            runtime = RuntimeRecord(id=str(uuid4()), key=runtime_key, name="Python Desktop", description=None, status="active")
            db.add(runtime)
            db.flush()

        runtime_row = db.scalar(
            select(RuntimeVersionRecord).where(
                RuntimeVersionRecord.runtime_id == runtime.id,
                RuntimeVersionRecord.version == runtime_version,
                RuntimeVersionRecord.operating_system == "windows",
                RuntimeVersionRecord.architecture == "x64",
            )
        )
        if runtime_row is None:
            runtime_row = RuntimeVersionRecord(
                id=str(uuid4()),
                runtime_id=runtime.id,
                version=runtime_version,
                operating_system="windows",
                architecture="x64",
                status="published",
                minimum_agent_version=None,
                supported_entrypoints=["python-function"],
                supported_execution_modes=["background", "interactive"],
                metadata_json={},
                published_at=now,
            )
            db.add(runtime_row)
            db.flush()
        else:
            runtime_row.status = "published"
            runtime_row.published_at = runtime_row.published_at or now
            db.add(runtime_row)

        automation = Automation(
            name=f"Smoke Execution {marker}",
            slug=f"smoke-execution-{marker}",
            key=f"smoke.execution.{marker}",
            description="Execution dispatch smoke automation.",
            category_id=category.id,
            executor_type="python_script",
            package_url=None,
            package_sha256=package_sha,
            default_priority="normal",
            timeout_seconds=300,
            max_retries=0,
            is_active=True,
            status="active",
            tags_json=["smoke"],
        )
        db.add(automation)
        db.flush()

        version = AutomationVersion(
            automation_id=automation.id,
            source_id=None,
            version="1.0.0",
            manifest=manifest,
            manifest_schema_version=1,
            runtime_id=runtime_key,
            runtime_version=runtime_version,
            entrypoint_type="python-function",
            entrypoint={"type": "python-function", "module": "application.main", "function": "run"},
            application_type="source",
            application_path=None,
            artifact_bucket="packages",
            artifact_object_key=f"smoke/{marker}.zip",
            artifact_size=1024,
            artifact_sha256=package_sha,
            source_commit_sha=None,
            source_path=None,
            status="published",
            published_at=now,
        )
        db.add(version)
        db.flush()

        manifest_row = AutomationManifestRecord(
            id=str(uuid4()),
            automation_version_id=version.id,
            schema_version="1.0",
            raw_content=json.dumps(manifest),
            normalized_content=manifest,
            content_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest(),
            validation_status="valid",
            validation_errors=None,
            validator_version="smoke",
            validated_at=now,
        )
        db.add(manifest_row)

        stored = StoredObjectRecord(
            id=str(uuid4()),
            bucket="packages",
            object_key=f"smoke/{marker}.zip",
            content_type="application/zip",
            size_bytes=1024,
            sha256=package_sha,
            etag=None,
            provider="local",
            status="available",
            verified_at=now,
        )
        db.add(stored)
        db.flush()

        package = AutomationPackageRecord(
            id=str(uuid4()),
            automation_version_id=version.id,
            stored_object_id=stored.id,
            package_format="zip",
            file_name=f"smoke-{marker}.zip",
            size_bytes=1024,
            sha256=package_sha,
            status="published",
            validation_result={"smoke": True},
            published_at=now,
        )
        db.add(package)
        db.flush()
        version.manifest_id = manifest_row.id
        version.package_id = package.id
        version.runtime_version_id = runtime_row.id
        db.add(version)
        db.commit()
        return version.id, automation.id


async def recv_type(ws, message_type: str, timeout: int = 8) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for {message_type}.")
        message = httpx.Response(200, content=await asyncio.wait_for(ws.recv(), timeout=remaining)).json()
        if message.get("message_type") == "portal.error":
            raise AssertionError(message["payload"])
        if message.get("message_type") == message_type:
            return message


async def create_execution(client: httpx.AsyncClient, headers: dict[str, str], version_id: int, agent_id: str) -> dict:
    response = await client.post(
        "/executions",
        headers={**headers, "Idempotency-Key": f"smoke-{uuid4().hex}"},
        json={"automation_version_id": version_id, "agent_id": agent_id, "parameters": {"source": "smoke"}, "priority": 0},
    )
    response.raise_for_status()
    return response.json()


async def main() -> None:
    version_id, automation_id = prepare_published_automation_version()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        login = await client.post("/auth/login", json={"email": "admin@portal.local", "password": "admin123"})
        login.raise_for_status()
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        token_response = await client.post("/agents/registration-tokens", headers=admin_headers, json={"expires_in_seconds": 600})
        token_response.raise_for_status()
        registration_token = token_response.json()["registration_token"]

        local_identity = f"execution-smoke-{uuid4().hex}"
        register_response = await client.post(
            "/agents/register",
            json={
                "registration_token": registration_token,
                "local_identity": local_identity,
                "hostname": "execution-smoke-agent",
                "name": "Execution Smoke Agent",
                "machine_fingerprint": local_identity,
                "agent_version": "1.0.0",
            },
        )
        register_response.raise_for_status()
        registered = register_response.json()
        agent_id = registered["agent"]["id"]
        bearer = registered["credential"]["bearer_token"]
        agent_instance_id = f"agi_exec_smoke_{uuid4().hex}"

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
            connected = await recv_type(ws, "agent.connected")
            assert connected["payload"]["selected_protocol_version"] == "1.0"

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "agent.heartbeat",
                        {
                            "observed_at": datetime.now(UTC).isoformat(),
                            "agent_version": "1.0.0",
                            "health": "healthy",
                            "resources": {
                                "cpu_percentage": 10,
                                "memory_total_mb": 4096,
                                "memory_available_mb": 2048,
                                "memory_percentage": 50,
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
            heartbeat_ack = await recv_type(ws, "portal.ack")
            assert heartbeat_ack["payload"]["result"]["ok"] is True

            first = await create_execution(client, admin_headers, version_id, agent_id)
            assert first["execution"]["status"] == "pending"
            offer_message = await recv_type(ws, "execution.offer")
            offer_payload = offer_message["payload"]
            assert offer_payload["execution_offer_id"] == first["current_offer"]["id"]

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "execution.accepted",
                        {
                            "execution_offer_id": offer_payload["execution_offer_id"],
                            "execution_attempt_id": offer_payload["execution_attempt_id"],
                            "agent_id": agent_id,
                            "agent_instance_id": agent_instance_id,
                            "accepted_at": datetime.now(UTC).isoformat(),
                        },
                        correlation_id=offer_message["message_id"],
                    )
                )
            )
            accepted_ack = await recv_type(ws, "portal.ack")
            assert accepted_ack["payload"]["result"]["commit_command_id"]

            commit_message = await recv_type(ws, "execution.commit")
            commit_payload = commit_message["payload"]
            assert commit_payload["execution_offer_id"] == offer_payload["execution_offer_id"]

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "agent.command.ack",
                        {
                            "command_id": commit_payload["command_id"],
                            "command_sequence": commit_payload["command_sequence"],
                            "status": "received",
                        },
                        correlation_id=commit_message["message_id"],
                    )
                )
            )
            command_ack = await recv_type(ws, "portal.ack")
            assert command_ack["payload"]["result"]["ok"] is True

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "execution.started",
                        {
                            "execution_offer_id": offer_payload["execution_offer_id"],
                            "execution_attempt_id": offer_payload["execution_attempt_id"],
                            "agent_id": agent_id,
                            "agent_instance_id": agent_instance_id,
                            "started_at": datetime.now(UTC).isoformat(),
                        },
                    )
                )
            )
            started_ack = await recv_type(ws, "portal.ack")
            assert started_ack["payload"]["result"]["status"] == "running"

            details_response = await client.get(f"/executions/{first['execution']['id']}", headers=admin_headers)
            details_response.raise_for_status()
            details = details_response.json()
            assert details["execution"]["status"] == "running"
            assert details["tasks"][0]["status"] == "running"
            assert details["current_attempt"]["status"] == "running"
            tasks_response = await client.get(f"/executions/{first['execution']['id']}/tasks", headers=admin_headers)
            tasks_response.raise_for_status()
            assert tasks_response.json()[0]["status"] == "running"
            attempts_response = await client.get(f"/executions/{first['execution']['id']}/attempts", headers=admin_headers)
            attempts_response.raise_for_status()
            assert attempts_response.json()[0]["status"] == "running"

            second = await create_execution(client, admin_headers, version_id, agent_id)
            rejected_offer_message = await recv_type(ws, "execution.offer")
            rejected_offer = rejected_offer_message["payload"]
            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "execution.rejected",
                        {
                            "execution_offer_id": rejected_offer["execution_offer_id"],
                            "execution_attempt_id": rejected_offer["execution_attempt_id"],
                            "agent_id": agent_id,
                            "agent_instance_id": agent_instance_id,
                            "rejection_code": "AGENT_OVERLOADED",
                            "rejection_details": {"reason": "smoke"},
                            "rejected_at": datetime.now(UTC).isoformat(),
                        },
                    )
                )
            )
            rejected_ack = await recv_type(ws, "portal.ack")
            assert rejected_ack["payload"]["result"]["status"] == "rejected"

            rejected_details_response = await client.get(f"/executions/{second['execution']['id']}", headers=admin_headers)
            rejected_details_response.raise_for_status()
            rejected_details = rejected_details_response.json()
            assert rejected_details["execution"]["status"] == "pending"
            assert rejected_details["tasks"][0]["status"] == "queued"
            assert rejected_details["current_attempt"]["status"] == "rejected"
            assert rejected_details["current_offer"]["status"] == "rejected"

            legacy_response = await client.post(
                "/jobs",
                headers=admin_headers,
                json={"automation_id": automation_id, "priority": "normal", "payload_json": {"source": "legacy-smoke"}},
            )
            legacy_response.raise_for_status()
            legacy_job = legacy_response.json()
            assert legacy_job["status"] == "queued"
            assert legacy_job["payload_json"]["_execution_id"].startswith("exe_")

            legacy_offer_message = await recv_type(ws, "execution.offer")
            legacy_offer = legacy_offer_message["payload"]
            assert legacy_offer["execution_offer_id"]
            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "execution.rejected",
                        {
                            "execution_offer_id": legacy_offer["execution_offer_id"],
                            "execution_attempt_id": legacy_offer["execution_attempt_id"],
                            "agent_id": agent_id,
                            "agent_instance_id": agent_instance_id,
                            "rejection_code": "AGENT_OVERLOADED",
                            "rejection_details": {"reason": "legacy-smoke"},
                            "rejected_at": datetime.now(UTC).isoformat(),
                        },
                    )
                )
            )
            legacy_rejected_ack = await recv_type(ws, "portal.ack")
            assert legacy_rejected_ack["payload"]["result"]["status"] == "rejected"

        await client.post(f"/agents/{agent_id}/disable", headers=admin_headers, json={"reason": "execution smoke complete"})

    print("execution dispatch smoke ok")


if __name__ == "__main__":
    asyncio.run(main())
