from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import websockets


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


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        login = await client.post("/auth/login", json={"email": "admin@portal.local", "password": "admin123"})
        login.raise_for_status()
        admin_token = login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        token_response = await client.post("/agents/registration-tokens", headers=admin_headers, json={"expires_in_seconds": 600})
        token_response.raise_for_status()
        registration_token = token_response.json()["registration_token"]

        local_identity = f"smoke-{uuid4().hex}"
        register_response = await client.post(
            "/agents/register",
            json={
                "registration_token": registration_token,
                "local_identity": local_identity,
                "hostname": "smoke-agent",
                "name": "Smoke Agent",
                "machine_fingerprint": local_identity,
                "agent_version": "1.0.0",
            },
        )
        register_response.raise_for_status()
        registered = register_response.json()
        agent_id = registered["agent"]["id"]
        bearer = registered["credential"]["bearer_token"]
        agent_instance_id = f"agi_smoke_{uuid4().hex}"

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
            connected = httpx.Response(200, content=await ws.recv()).json()
            assert connected["message_type"] == "agent.connected"

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
                                "cpu_percentage": 12,
                                "memory_total_mb": 4096,
                                "memory_available_mb": 2048,
                                "memory_percentage": 50,
                                "disk_free_mb": 100000,
                            },
                            "interactive_session": {"available": True, "locked": False, "user": "SMOKE\\agent", "session_id": 1},
                            "pools": {
                                "interactive": {"total": 1, "used": 0, "reserved": 0},
                                "background": {"total": 2, "used": 0, "reserved": 0},
                                "browser": {"total": 1, "used": 0, "reserved": 0},
                            },
                        },
                    )
                )
            )
            heartbeat_ack = httpx.Response(200, content=await ws.recv()).json()
            assert heartbeat_ack["payload"]["ok"] is True

            diagnostic = await client.post(f"/agents/{agent_id}/diagnostics", headers=admin_headers, json={"payload": {"reason": "smoke"}})
            diagnostic.raise_for_status()
            command = diagnostic.json()["command"]

            command_envelope = httpx.Response(200, content=await asyncio.wait_for(ws.recv(), timeout=6)).json()
            assert command_envelope["message_type"] == "agent.diagnostic.request"
            assert command_envelope["payload"]["command_id"] == command["id"]

            await ws.send(
                json.dumps(
                    envelope(
                        agent_id,
                        agent_instance_id,
                        "agent.command.ack",
                        {
                            "command_id": command["id"],
                            "command_sequence": command["command_sequence"],
                            "status": "received",
                        },
                        correlation_id=command_envelope["message_id"],
                    )
                )
            )
            command_ack = httpx.Response(200, content=await ws.recv()).json()
            assert command_ack["payload"]["ok"] is True

        agent_response = await client.get(f"/agents/{agent_id}", headers=admin_headers)
        agent_response.raise_for_status()
        assert agent_response.json()["last_seen_at"] is not None

        disable_response = await client.post(f"/agents/{agent_id}/disable", headers=admin_headers, json={"reason": "smoke complete"})
        disable_response.raise_for_status()

        try:
            async with websockets.connect(WS_URL, additional_headers={"Authorization": f"Bearer {bearer}"}) as ws:
                rejected = httpx.Response(200, content=await ws.recv()).json()
                assert rejected["payload"]["code"] == "AUTHENTICATION_FAILED"
        except websockets.exceptions.ConnectionClosed:
            pass

    print("gateway smoke ok")


if __name__ == "__main__":
    asyncio.run(main())
