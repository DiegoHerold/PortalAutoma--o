from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from modules.catalog.application.dto import ActorDTO, CategoryDTO
from modules.catalog.application.ports import AuditRecorder, CatalogRepository, OutboxPort, TransactionManager
from modules.catalog.domain.errors import CatalogValidationError, DuplicateAutomationKeyError
from modules.catalog.domain.events import automation_event
from modules.governance.domain.audit import AuditEvent


@dataclass
class ListCategories:
    catalog: CatalogRepository

    def execute(self) -> list[CategoryDTO]:
        return self.catalog.list_categories()


@dataclass
class GetCategory:
    catalog: CatalogRepository

    def execute(self, category_id: int) -> CategoryDTO:
        category = self.catalog.get_category(category_id)
        if category is None:
            raise CatalogValidationError("Category not found.")
        return category


@dataclass
class CreateCategory:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, payload: dict[str, Any], actor: ActorDTO) -> CategoryDTO:
        slug = _normalize_slug(payload["slug"])
        if self.catalog.get_category_by_slug(slug) is not None:
            raise DuplicateAutomationKeyError(f"Category slug already exists: {slug}")
        category = self.catalog.create_category({**payload, "slug": slug})
        self._audit(actor, "category.created", category, after={"slug": category.slug, "name": category.name})
        self.outbox.append_catalog_event(automation_event("category.created", str(category.id), {"slug": category.slug}))
        self.transaction.commit()
        return category

    def _audit(self, actor: ActorDTO, action: str, category: CategoryDTO, before: dict | None = None, after: dict | None = None) -> None:
        self.audit.append(_audit_event(actor, action, category, before=before, after=after))


@dataclass
class UpdateCategory:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, category_id: int, payload: dict[str, Any], actor: ActorDTO) -> CategoryDTO:
        before = self.catalog.get_category(category_id)
        if before is None:
            raise CatalogValidationError("Category not found.")
        if "slug" in payload and payload["slug"]:
            slug = _normalize_slug(payload["slug"])
            existing = self.catalog.get_category_by_slug(slug)
            if existing is not None and existing.id != category_id:
                raise DuplicateAutomationKeyError(f"Category slug already exists: {slug}")
            payload = {**payload, "slug": slug}
        category = self.catalog.update_category(category_id, payload)
        self.audit.append(
            _audit_event(
                actor,
                "category.updated",
                category,
                before={"slug": before.slug, "name": before.name, "is_active": before.is_active},
                after={"slug": category.slug, "name": category.name, "is_active": category.is_active},
            )
        )
        self.outbox.append_catalog_event(automation_event("category.updated", str(category.id), {"slug": category.slug}))
        self.transaction.commit()
        return category


@dataclass
class ArchiveCategory:
    catalog: CatalogRepository
    audit: AuditRecorder
    outbox: OutboxPort
    transaction: TransactionManager

    def execute(self, category_id: int, actor: ActorDTO) -> CategoryDTO:
        before = self.catalog.get_category(category_id)
        if before is None:
            raise CatalogValidationError("Category not found.")
        category = self.catalog.archive_category(category_id)
        self.audit.append(
            _audit_event(
                actor,
                "category.archived",
                category,
                before={"is_active": before.is_active},
                after={"is_active": category.is_active},
            )
        )
        self.outbox.append_catalog_event(automation_event("category.archived", str(category.id), {"slug": category.slug}))
        self.transaction.commit()
        return category


def _normalize_slug(value: str) -> str:
    slug = str(value).strip().lower()
    if not slug:
        raise CatalogValidationError("Category slug is required.")
    return slug


def _audit_event(
    actor: ActorDTO,
    action: str,
    category: CategoryDTO,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=str(uuid4()),
        actor_type=actor.actor_type,
        actor_id=actor.actor_id or actor.actor_email,
        action=action,
        resource_type="category",
        resource_id=str(category.id),
        before=before,
        after=after,
    )
