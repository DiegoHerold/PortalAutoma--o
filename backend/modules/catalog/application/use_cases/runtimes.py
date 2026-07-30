from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, RuntimeDTO, RuntimeVersionDTO
from modules.catalog.application.ports import AuditRecorder, CatalogRepository, OutboxPort, TransactionManager
from modules.catalog.domain.errors import CatalogValidationError
from modules.catalog.domain.events import CatalogEvent
from modules.governance.domain.audit import AuditEvent


@dataclass
class ListRuntimes:
    catalog: CatalogRepository

    def execute(self) -> list[RuntimeDTO]:
        return self.catalog.list_runtimes()


@dataclass
class GetRuntime:
    catalog: CatalogRepository

    def execute(self, runtime_id: str) -> RuntimeDTO:
        runtime = self.catalog.get_runtime(runtime_id)
        if runtime is None:
            raise CatalogValidationError("Runtime not found.")
        return runtime


@dataclass
class CreateRuntime:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, payload: dict[str, Any], actor: ActorDTO) -> RuntimeDTO:
        key = payload.get("key")
        if not isinstance(key, str) or not key:
            raise CatalogValidationError("Runtime key is required.")
        if self.catalog.get_runtime_by_key(key) is not None:
            raise CatalogValidationError(f"Runtime already exists: {key}")
        runtime = self.catalog.create_runtime(payload)
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="runtime.created",
                resource_type="runtime",
                resource_id=runtime.id,
                after={"key": runtime.key},
            )
        )
        self.outbox.append_catalog_event(
            CatalogEvent("runtime.created", "Runtime", runtime.id, {"key": runtime.key})
        )
        self.transaction.commit()
        return runtime


@dataclass
class CreateRuntimeVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, runtime_id: str, payload: dict[str, Any], actor: ActorDTO) -> RuntimeVersionDTO:
        if self.catalog.get_runtime(runtime_id) is None:
            raise CatalogValidationError("Runtime not found.")
        version = self.catalog.create_runtime_version({"runtime_id": runtime_id, **payload})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="runtime_version.created",
                resource_type="runtime_version",
                resource_id=version.id,
                after={"runtime_id": runtime_id, "version": version.version},
            )
        )
        self.outbox.append_catalog_event(
            CatalogEvent("runtime_version.created", "RuntimeVersion", version.id, {"runtime_id": runtime_id})
        )
        self.transaction.commit()
        return version


@dataclass
class ListRuntimeVersions:
    catalog: CatalogRepository

    def execute(self, runtime_id: str) -> list[RuntimeVersionDTO]:
        if self.catalog.get_runtime(runtime_id) is None:
            raise CatalogValidationError("Runtime not found.")
        return self.catalog.list_runtime_versions(runtime_id)


@dataclass
class GetRuntimeVersion:
    catalog: CatalogRepository

    def execute(self, runtime_version_id: str) -> RuntimeVersionDTO:
        version = self.catalog.get_runtime_version(runtime_version_id)
        if version is None:
            raise CatalogValidationError("RuntimeVersion not found.")
        return version


@dataclass
class PublishRuntimeVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, runtime_version_id: str, actor: ActorDTO) -> RuntimeVersionDTO:
        version = self.catalog.get_runtime_version(runtime_version_id)
        if version is None:
            raise CatalogValidationError("RuntimeVersion not found.")
        if version.status in {"deprecated", "blocked"}:
            raise CatalogValidationError("Deprecated or blocked RuntimeVersions cannot be published.")
        updated = self.catalog.update_runtime_version(runtime_version_id, {"status": "published"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="runtime_version.published",
                resource_type="runtime_version",
                resource_id=runtime_version_id,
            )
        )
        self.outbox.append_catalog_event(CatalogEvent("runtime_version.published", "RuntimeVersion", runtime_version_id, {}))
        self.transaction.commit()
        return updated


@dataclass
class DeprecateRuntimeVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, runtime_version_id: str, actor: ActorDTO) -> RuntimeVersionDTO:
        updated = self.catalog.update_runtime_version(runtime_version_id, {"status": "deprecated"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="runtime_version.deprecated",
                resource_type="runtime_version",
                resource_id=runtime_version_id,
            )
        )
        self.outbox.append_catalog_event(CatalogEvent("runtime_version.deprecated", "RuntimeVersion", runtime_version_id, {}))
        self.transaction.commit()
        return updated


@dataclass
class BlockRuntimeVersion:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, runtime_version_id: str, actor: ActorDTO, reason: str | None = None) -> RuntimeVersionDTO:
        updated = self.catalog.update_runtime_version(runtime_version_id, {"status": "blocked"})
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="runtime_version.blocked",
                resource_type="runtime_version",
                resource_id=runtime_version_id,
                metadata={"reason": reason},
            )
        )
        self.outbox.append_catalog_event(CatalogEvent("runtime_version.blocked", "RuntimeVersion", runtime_version_id, {"reason": reason}))
        self.transaction.commit()
        return updated
