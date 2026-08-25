from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modules.dispatch.application.use_cases.scheduler import _enrich_requirements, _execution_offer_payload
from modules.orchestration.application.dto import AutomationVersionSnapshotDTO, ExecutionOfferDTO, TaskExecutionDTO


def test_execution_offer_payload_includes_package_download_url() -> None:
    now = datetime.now(UTC)
    offer = ExecutionOfferDTO(
        id="off_1",
        execution_attempt_id="att_1",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        status="pending",
        requirements_snapshot={},
        offered_at=now,
        expires_at=now + timedelta(seconds=60),
    )
    task = TaskExecutionDTO(
        id="task_1",
        execution_id="exe_1",
        automation_version_id=42,
        status="queued",
        priority=0,
        parameters={"message": "hello"},
        input={"parameters": {"message": "hello"}},
        result=None,
        retry_policy={},
        timeout_policy={},
        created_at=now,
    )
    requirements = {
        "automation_id": 10,
        "automation_key": "certification.echo",
        "automation_name": "Certification Echo",
        "automation_version": "1.0.0",
        "execution_mode": "background",
        "runtime": {"id": "python-core", "version": "3.13"},
        "package": {
            "id": "pkg_1",
            "download_url": "http://portal.local/api/v1/automations/artifacts/download?token=abc",
            "sha256": "a" * 64,
            "size_bytes": 123,
        },
        "resource_requirements": {"cpu_units": 1, "memory_mb": 512, "disk_mb": 100},
        "required_capabilities": [{"key": "agent.background_execution"}],
        "required_pools": ["background"],
        "exclusive_resources": [],
    }

    payload = _execution_offer_payload(offer, task, requirements)

    assert payload["automation_version_id"] == "42"
    assert payload["automation_id"] == "10"
    assert payload["package"]["download_url"].endswith("token=abc")
    assert payload["package"]["sha256"] == "a" * 64


def test_enrich_requirements_restores_missing_package_download_url() -> None:
    version = AutomationVersionSnapshotDTO(
        automation_id=10,
        automation_key="certification.echo",
        automation_name="Certification Echo",
        automation_version_id=42,
        version="1.0.0",
        status="published",
        runtime_id="python-core",
        runtime_version="3.13",
        runtime_version_id="rtv_1",
        package_id="pkg_1",
        package_sha256="b" * 64,
        package_size_bytes=456,
        package_download_url="http://portal.local/api/v1/automations/artifacts/download?token=xyz",
        manifest={},
        execution_mode="background",
        timeout_seconds=300,
        resources={"cpu_units": 1, "memory_mb": 512, "disk_mb": 100},
        required_capabilities=[],
        required_pools=["background"],
        exclusive_resources=[],
    )

    enriched = _enrich_requirements({"package": {"id": "pkg_1", "sha256": "b" * 64, "size_bytes": 456}}, version)

    assert enriched["package"]["download_url"].endswith("token=xyz")
