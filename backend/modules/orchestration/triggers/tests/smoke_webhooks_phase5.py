from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from infrastructure.database import SessionLocal
from main import app
from modules.access.api.dependencies import get_current_user
from modules.access.infrastructure.orm.models import AccessUserCategoryPermissionRecord
from modules.catalog.infrastructure.orm.models import (
    AutomationPackageRecord,
    CatalogAutomationRecord,
    CatalogAutomationVersionRecord,
    CatalogCategoryRecord,
    RuntimeRecord,
    RuntimeVersionRecord,
)
from modules.dispatch.infrastructure.orm.models import DispatchDecisionRecord
from modules.orchestration.infrastructure.orm.models import (
    LegacyJobMirrorRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
    TriggerCompatRecord,
)
from modules.shared.infrastructure.orm.models import IdempotencyRecordModel
from modules.storage.infrastructure.orm.models import StoredObjectRecord
from modules.telemetry.infrastructure.orm.models import OutboxMessageRecord


def _admin():
    return SimpleNamespace(
        id=1,
        email="smoke@example.local",
        role="admin",
        role_id=None,
        organization_id=None,
        rbac_permissions=[],
        category_permissions=[],
    )


def _seed():
    suffix = uuid4().hex[:10]
    now = datetime.now(UTC)
    with SessionLocal() as db:
        category = CatalogCategoryRecord(name=f"Smoke Phase 5 {suffix}", slug=f"smoke-phase5-{suffix}", is_active=True)
        db.add(category)
        db.flush()

        automation = CatalogAutomationRecord(
            name=f"Smoke Webhook {suffix}",
            slug=f"smoke-webhook-{suffix}",
            key=f"smoke-webhook-{suffix}",
            category_id=category.id,
            executor_type="python_script",
            default_priority="normal",
            timeout_seconds=60,
            max_retries=0,
            is_active=True,
            status="active",
            tags_json=[],
        )
        db.add(automation)
        db.flush()

        runtime = RuntimeRecord(id=str(uuid4()), key=f"smoke-runtime-{suffix}", name=f"Smoke Runtime {suffix}", status="active")
        db.add(runtime)
        runtime_version = RuntimeVersionRecord(
            id=str(uuid4()),
            runtime_id=runtime.id,
            version="1.0.0",
            operating_system="linux",
            architecture="x64",
            status="published",
            supported_entrypoints=["python-function"],
            supported_execution_modes=["background"],
            metadata_json={},
            published_at=now,
        )
        db.add(runtime_version)
        db.flush()

        stored = StoredObjectRecord(
            id=str(uuid4()),
            bucket="smoke",
            object_key=f"{suffix}/package.zip",
            content_type="application/zip",
            size_bytes=1,
            sha256="a" * 64,
            provider="local",
            status="available",
            verified_at=now,
        )
        db.add(stored)
        db.flush()

        version = CatalogAutomationVersionRecord(
            automation_id=automation.id,
            version="1.0.0",
            manifest={
                "execution": {"mode": "background", "timeout_seconds": 60},
                "resources": {"cpu_units": 1, "memory_mb": 128, "disk_mb": 10},
                "capabilities": {"required": []},
            },
            manifest_schema_version=1,
            runtime_id=runtime.key,
            runtime_version=runtime_version.version,
            runtime_version_id=runtime_version.id,
            entrypoint_type="python-function",
            entrypoint={"module": "main", "callable": "run"},
            application_type="source",
            artifact_bucket="smoke",
            artifact_object_key=f"{suffix}/package.zip",
            artifact_size=1,
            artifact_sha256="a" * 64,
            status="published",
            published_at=now,
        )
        db.add(version)
        db.flush()

        package = AutomationPackageRecord(
            id=str(uuid4()),
            automation_version_id=version.id,
            stored_object_id=stored.id,
            package_format="zip",
            file_name="package.zip",
            size_bytes=1,
            sha256="a" * 64,
            status="published",
            published_at=now,
        )
        db.add(package)
        db.flush()
        version.package_id = package.id
        db.add(version)
        db.commit()
        return {
            "suffix": suffix,
            "category_id": category.id,
            "automation_id": automation.id,
            "version_id": version.id,
            "package_id": package.id,
            "stored_object_id": stored.id,
            "runtime_id": runtime.id,
            "runtime_version_id": runtime_version.id,
        }


def _cleanup(seed: dict, trigger_ids: list[int], execution_ids: list[str]) -> None:
    with SessionLocal() as db:
        task_ids = db.scalars(select(TaskExecutionRecord.id).where(TaskExecutionRecord.execution_id.in_(execution_ids or [""]))).all()
        job_ids = db.scalars(select(LegacyJobMirrorRecord.id).where(LegacyJobMirrorRecord.trigger_id.in_(trigger_ids or [-1]))).all()
        db.execute(delete(DispatchDecisionRecord).where(DispatchDecisionRecord.task_execution_id.in_(task_ids or [""])))
        db.execute(delete(OutboxMessageRecord).where(OutboxMessageRecord.aggregate_id.in_([*execution_ids, *task_ids])))
        db.execute(delete(LegacyJobMirrorRecord).where(LegacyJobMirrorRecord.id.in_(job_ids or [-1])))
        db.execute(delete(TaskExecutionRecord).where(TaskExecutionRecord.id.in_(task_ids or [""])))
        db.execute(delete(OrchestrationExecutionRecord).where(OrchestrationExecutionRecord.id.in_(execution_ids or [""])))
        db.execute(delete(IdempotencyRecordModel).where(IdempotencyRecordModel.key.like("trigger:%:smoke-phase5-%")))
        db.execute(delete(TriggerCompatRecord).where(TriggerCompatRecord.id.in_(trigger_ids or [-1])))
        db.execute(update(CatalogAutomationVersionRecord).where(CatalogAutomationVersionRecord.id == seed["version_id"]).values(package_id=None))
        db.execute(delete(AutomationPackageRecord).where(AutomationPackageRecord.id == seed["package_id"]))
        db.execute(delete(CatalogAutomationVersionRecord).where(CatalogAutomationVersionRecord.id == seed["version_id"]))
        db.execute(delete(StoredObjectRecord).where(StoredObjectRecord.id == seed["stored_object_id"]))
        db.execute(delete(RuntimeVersionRecord).where(RuntimeVersionRecord.id == seed["runtime_version_id"]))
        db.execute(delete(RuntimeRecord).where(RuntimeRecord.id == seed["runtime_id"]))
        db.execute(delete(CatalogAutomationRecord).where(CatalogAutomationRecord.id == seed["automation_id"]))
        db.execute(delete(AccessUserCategoryPermissionRecord).where(AccessUserCategoryPermissionRecord.category_id == seed["category_id"]))
        db.execute(delete(CatalogCategoryRecord).where(CatalogCategoryRecord.id == seed["category_id"]))
        db.commit()


def main() -> None:
    seed = _seed()
    trigger_ids: list[int] = []
    execution_ids: list[str] = []
    app.dependency_overrides[get_current_user] = _admin
    client = TestClient(app)
    route_path = f"smoke-phase5-{seed['suffix']}"

    try:
        created = client.post(
            "/api/v1/triggers",
            json={
                "name": "Smoke Phase 5",
                "automation_id": seed["automation_id"],
                "trigger_type": "https",
                "route_path": route_path,
                "is_active": True,
                "parameter_mapping_json": {
                    "company_id": "body.company_id",
                    "customer": "headers.x-customer",
                    "force": "query_params.force",
                },
            },
        )
        assert created.status_code == 201, created.text
        created_body = created.json()
        trigger_id = int(created_body["id"])
        trigger_ids.append(trigger_id)
        first_secret = created_body["secret_token"]
        assert first_secret and first_secret.startswith("whsec_")

        listed = client.get("/api/v1/triggers")
        assert listed.status_code == 200, listed.text
        assert "secret_token" not in listed.text

        detail = client.get(f"/api/v1/triggers/{trigger_id}")
        assert detail.status_code == 200, detail.text
        assert "secret_token" not in detail.text
        assert detail.json()["invocation_url"].endswith(f"/api/v1/triggers/invoke/{route_path}")

        updated = client.put(
            f"/api/v1/triggers/{trigger_id}",
            json={
                "name": "Smoke Phase 5 Updated",
                "automation_id": seed["automation_id"],
                "trigger_type": "https",
                "route_path": route_path,
                "is_active": True,
                "parameter_mapping_json": {"company_id": "body.company_id"},
            },
        )
        assert updated.status_code == 200, updated.text

        duplicate = client.post(
            "/api/v1/triggers",
            json={
                "automation_id": seed["automation_id"],
                "trigger_type": "https",
                "route_path": route_path,
            },
        )
        assert duplicate.status_code == 409, duplicate.text

        before_dry_run = client.get(f"/api/v1/executions?origin=trigger&trigger_id={trigger_id}")
        assert before_dry_run.status_code == 200, before_dry_run.text
        dry_run = client.post(
            f"/api/v1/triggers/{trigger_id}/test",
            json={
                "sample_payload": {"company_id": 123},
                "sample_headers": {"x-customer": "cliente-a"},
                "sample_query_params": {"force": "true"},
            },
        )
        assert dry_run.status_code == 200, dry_run.text
        assert dry_run.json()["parameters"] == {"company_id": 123}
        after_dry_run = client.get(f"/api/v1/executions?origin=trigger&trigger_id={trigger_id}")
        assert after_dry_run.status_code == 200, after_dry_run.text
        assert len(after_dry_run.json()) == len(before_dry_run.json())

        invoked = client.post(
            f"/api/v1/triggers/invoke/{route_path}",
            json={"company_id": 456},
            headers={
                "X-Trigger-Secret": first_secret,
                "Idempotency-Key": f"smoke-phase5-{seed['suffix']}-1",
                "X-Correlation-ID": f"smoke-phase5-{seed['suffix']}",
            },
        )
        assert invoked.status_code == 200, invoked.text
        execution_ids.append(invoked.json()["execution_id"])
        assert invoked.json()["correlation_id"] == f"smoke-phase5-{seed['suffix']}"

        related = client.get(f"/api/v1/executions?origin=trigger&trigger_id={trigger_id}")
        assert related.status_code == 200, related.text
        assert any(item["id"] == invoked.json()["execution_id"] and item["trigger_id"] == trigger_id for item in related.json())

        rotated = client.post(f"/api/v1/triggers/{trigger_id}/rotate-secret")
        assert rotated.status_code == 200, rotated.text
        second_secret = rotated.json()["secret_token"]
        assert second_secret and second_secret != first_secret

        old_secret = client.post(f"/api/v1/triggers/invoke/{route_path}", json={"company_id": 789}, headers={"X-Trigger-Secret": first_secret})
        assert old_secret.status_code == 401, old_secret.text

        second_invoke = client.post(
            f"/api/v1/triggers/invoke/{route_path}",
            json={"company_id": 789},
            headers={"X-Trigger-Secret": second_secret, "Idempotency-Key": f"smoke-phase5-{seed['suffix']}-2"},
        )
        assert second_invoke.status_code == 200, second_invoke.text
        execution_ids.append(second_invoke.json()["execution_id"])

        disabled = client.put(
            f"/api/v1/triggers/{trigger_id}",
            json={
                "name": "Smoke Phase 5 Disabled",
                "automation_id": seed["automation_id"],
                "trigger_type": "https",
                "route_path": route_path,
                "is_active": False,
                "parameter_mapping_json": {"company_id": "body.company_id"},
            },
        )
        assert disabled.status_code == 200, disabled.text
        inactive = client.post(f"/api/v1/triggers/invoke/{route_path}", json={"company_id": 999}, headers={"X-Trigger-Secret": second_secret})
        assert inactive.status_code == 409, inactive.text

        deleted = client.delete(f"/api/v1/triggers/{trigger_id}")
        assert deleted.status_code == 204, deleted.text
        trigger_ids.remove(trigger_id)
        print("smoke_webhooks_phase5 ok")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        _cleanup(seed, trigger_ids, execution_ids)


if __name__ == "__main__":
    main()
