from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.services.import_staging_store import delete_staging_entry, get_staging_entry
from modules.catalog.application.dto import ActorDTO
from modules.catalog.application.use_cases import ConfirmStagedAutomationImport
from modules.catalog.domain.errors import CatalogValidationError, DuplicateAutomationVersionError
from modules.catalog.infrastructure.adapters import build_catalog_adapters


class DuplicateVersionError(Exception):
    """Raised when confirming a staged import whose (automation_id, version) already exists."""


class StagingNotFoundError(Exception):
    """Raised when a staging_id is missing or has expired."""


class AutomationImportService:
    """Compatibility facade for staged GitHub/manual imports.

    Staging is still produced by legacy adapters, but Catalog persistence,
    manifest/package records, audit and outbox are handled by
    `ConfirmStagedAutomationImport` in `backend/modules/catalog`.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)
        self.adapters = build_catalog_adapters(db)

    def _slugify(self, value: str) -> str:
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "automation"

    def _resolve_category(self, category_name: str | None, category_id: int | None) -> Category:
        if category_id is not None:
            category = self.categories.get(category_id)
            if category is None:
                raise ValueError("Categoria informada nao encontrada.")
            return category
        if category_name:
            existing = next(
                (category for category in self.categories.list_all() if category.name.lower() == category_name.lower()),
                None,
            )
            if existing:
                return existing
            category = Category(name=category_name, slug=self._slugify(category_name), is_active=True)
            self.db.add(category)
            self.db.flush()
            return category
        raise ValueError("Informe category_id ou uma categoria no manifesto.")

    def confirm(self, staging_id: str, user: User, category_id: int | None = None):
        staged = get_staging_entry(staging_id)
        if staged is None:
            raise StagingNotFoundError(f"Importacao {staging_id} nao encontrada ou expirada.")

        manifest = staged["manifest"]
        category = self._resolve_category(manifest.get("category"), category_id)
        try:
            version = ConfirmStagedAutomationImport(
                self.adapters.catalog,
                self.adapters.stored_objects,
                self.adapters.audit,
                self.adapters.outbox,
                self.adapters.transaction,
            ).execute(staged, _actor(user), category.id)
        except DuplicateAutomationVersionError as exc:
            self.db.rollback()
            raise DuplicateVersionError(str(exc)) from exc
        except CatalogValidationError as exc:
            self.db.rollback()
            raise ValueError(str(exc)) from exc
        delete_staging_entry(staging_id)
        return version

    def discard(self, staging_id: str) -> None:
        delete_staging_entry(staging_id)


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)
