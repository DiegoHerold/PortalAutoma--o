from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import httpx

from modules.orchestration.tests.smoke_execution_dispatch_flow import prepare_published_automation_version


BASE_URL = "http://localhost:8000/api/v1"


def _raise(response: httpx.Response) -> dict:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AssertionError(f"{response.request.method} {response.request.url} failed: {response.text}") from exc
    return response.json()


def main() -> None:
    automation_version_id, _, _ = prepare_published_automation_version()
    marker = uuid4().hex[:12]

    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        login = _raise(client.post("/auth/login", json={"email": "admin@portal.local", "password": "admin123"}))
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        flow = _raise(
            client.post(
                "/flows",
                headers=headers,
                json={"key": f"smoke.flow.{marker}", "name": f"Smoke Flow {marker}", "tags": ["smoke"]},
            )
        )
        flow_id = flow["id"]

        version = _raise(
            client.post(
                f"/flows/{flow_id}/versions",
                headers=headers,
                json={
                    "version": "1.0.0",
                    "definition": {
                        "output_mapping": {
                            "company": {"source": "flow.input", "path": "$.company"},
                        },
                    },
                },
            )
        )
        flow_version_id = version["id"]

        node = _raise(
            client.post(
                f"/flow-versions/{flow_version_id}/nodes",
                headers=headers,
                json={
                    "key": "run",
                    "name": "Run automation",
                    "node_type": "automation",
                    "automation_version_id": automation_version_id,
                    "input_mapping": {
                        "company": {"source": "flow.input", "path": "$.company"},
                        "mode": {"value": "api-smoke"},
                    },
                    "position_metadata": {"x": 120, "y": 80},
                },
            )
        )

        validation = _raise(client.post(f"/flow-versions/{flow_version_id}/validate", headers=headers))
        assert validation["valid"] is True
        assert node["id"] in validation["topological_order"]

        published = _raise(client.post(f"/flow-versions/{flow_version_id}/publish", headers=headers))
        assert published["status"] == "published"

        flow_execution = _raise(
            client.post(
                "/flow-executions",
                headers=headers,
                json={"flow_version_id": flow_version_id, "input": {"company": "ACME"}, "origin": "manual"},
            )
        )
        assert flow_execution["flow_execution"]["execution_id"].startswith("exe_")
        assert flow_execution["flow_execution"]["status"] == "running"
        assert flow_execution["node_executions"][0]["status"] == "running"
        assert flow_execution["node_executions"][0]["task_execution_id"].startswith("task_")

        timeline = client.get(f"/flow-executions/{flow_execution['flow_execution']['id']}/timeline", headers=headers)
        assert timeline.status_code == 200

        schedule = _raise(
            client.post(
                "/schedules",
                headers=headers,
                json={
                    "target_type": "flow",
                    "flow_version_id": flow_version_id,
                    "key": f"smoke.schedule.{marker}",
                    "name": f"Smoke Schedule {marker}",
                    "schedule_type": "once",
                    "recurrence_type": "once",
                    "specific_date": date.today().isoformat(),
                    "time_of_day": (datetime.now() + timedelta(minutes=5)).strftime("%H:%M"),
                    "timezone": "America/Sao_Paulo",
                    "payload": {"company": "Scheduled ACME"},
                    "overlap_policy": "allow",
                },
            )
        )
        assert schedule["target_type"] == "flow"
        assert schedule["flow_version_id"] == flow_version_id

        schedule_execution = _raise(client.post(f"/schedules/{schedule['id']}/trigger", headers=headers))
        assert schedule_execution["status"] == "running"
        assert schedule_execution["flow_execution_id"].startswith("flx_")
        assert schedule_execution["execution_id"].startswith("exe_")

        history = _raise(client.get(f"/schedules/{schedule['id']}/history", headers=headers))
        assert any(item["id"] == schedule_execution["id"] for item in history)

        fetched = _raise(client.get(f"/schedule-executions/{schedule_execution['id']}", headers=headers))
        assert fetched["id"] == schedule_execution["id"]

        patched = _raise(client.patch(f"/schedules/{schedule['id']}", headers=headers, json={"name": f"Patched {marker}"}))
        assert patched["name"] == f"Patched {marker}"
        assert patched["flow_version_id"] == flow_version_id

    print("flow/schedule api smoke ok")


if __name__ == "__main__":
    main()
