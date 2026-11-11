from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, AutomationDTO
from modules.catalog.application.ports import AuditRecorder, CatalogRepository, OutboxPort, TransactionManager
from modules.catalog.domain.errors import DuplicateAutomationKeyError, CatalogValidationError
from modules.catalog.domain.events import automation_event
from modules.catalog.domain.value_objects import AutomationKey
from modules.governance.domain.audit import AuditEvent


@dataclass
class ListAutomations:
    catalog: CatalogRepository

    def execute(self) -> list[AutomationDTO]:
        return self.catalog.list_automations()


@dataclass
class GetAutomation:
    catalog: CatalogRepository

    def execute(self, automation_id: int) -> AutomationDTO:
        automation = self.catalog.get_automation(automation_id)
        if automation is None:
            raise CatalogValidationError("Automation not found.")
        return automation


@dataclass
class CreateAutomation:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, payload: dict[str, Any], actor: ActorDTO) -> AutomationDTO:
        key = payload.get("key") or payload.get("slug")
        if not isinstance(key, str):
            raise CatalogValidationError("Automation key or slug is required.")
        AutomationKey(key)
        if self.catalog.get_automation_by_key(key) is not None:
            raise DuplicateAutomationKeyError(f"Automation key already exists: {key}")
        slug = payload.get("slug")
        if isinstance(slug, str) and self.catalog.get_automation_by_slug(slug) is not None:
            raise DuplicateAutomationKeyError(f"Automation slug already exists: {slug}")

        automation = self.catalog.create_automation(
            {
                **payload,
                "key": key,
                "status": payload.get("status") or ("active" if payload.get("is_active", True) else "disabled"),
                "created_by": actor.actor_id,
            }
        )
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation.created",
                resource_type="automation",
                resource_id=str(automation.id),
                after={"key": automation.key, "name": automation.name},
            )
        )
        self.outbox.append_catalog_event(
            automation_event("automation.created", str(automation.id), {"key": automation.key, "name": automation.name})
        )
        self.transaction.commit()
        return automation


@dataclass
class UpdateAutomationMetadata:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, payload: dict[str, Any], actor: ActorDTO) -> AutomationDTO:
        before = self.catalog.get_automation(automation_id)
        if before is None:
            raise CatalogValidationError("Automation not found.")
        if "key" in payload and payload["key"] and payload["key"] != before.key:
            raise CatalogValidationError("Automation key is immutable.")
        automation = self.catalog.update_automation(automation_id, payload)
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation.updated",
                resource_type="automation",
                resource_id=str(automation.id),
                before={"name": before.name, "description": before.description, "status": before.status},
                after={"name": automation.name, "description": automation.description, "status": automation.status},
            )
        )
        self.outbox.append_catalog_event(
            automation_event("automation.updated", str(automation.id), {"key": automation.key, "name": automation.name})
        )
        self.transaction.commit()
        return automation


@dataclass
class RestoreAutomation:
    """Volta uma automação arquivada para o Catálogo (o histórico nunca saiu)."""

    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, actor: ActorDTO) -> AutomationDTO:
        before = self.catalog.get_automation(automation_id)
        if before is None:
            raise CatalogValidationError("Automation not found.")
        automation = self.catalog.restore_automation(automation_id)
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation.restored",
                resource_type="automation",
                resource_id=str(automation.id),
                before={"status": before.status},
                after={"status": automation.status},
            )
        )
        self.outbox.append_catalog_event(
            automation_event("automation.restored", str(automation.id), {"key": automation.key})
        )
        self.transaction.commit()
        return automation


@dataclass
class ArchiveAutomation:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, automation_id: int, actor: ActorDTO) -> AutomationDTO:
        before = self.catalog.get_automation(automation_id)
        if before is None:
            raise CatalogValidationError("Automation not found.")
        automation = self.catalog.archive_automation(automation_id)
        self.audit.append(
            AuditEvent(
                id=str(uuid4()),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id or actor.actor_email,
                action="automation.archived",
                resource_type="automation",
                resource_id=str(automation.id),
                before={"status": before.status},
                after={"status": automation.status},
            )
        )
        self.outbox.append_catalog_event(
            automation_event("automation.archived", str(automation.id), {"key": automation.key})
        )
        self.transaction.commit()
        return automation
