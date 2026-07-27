from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from modules.catalog.application.dto import ActorDTO
from modules.catalog.application.use_cases import (
    DeprecateAutomationVersion,
    ListAutomationVersions,
    PublishAutomationVersion,
)
from modules.catalog.domain.errors import CatalogValidationError
from modules.catalog.infrastructure.adapters import build_catalog_adapters


class AutomationVersionLifecycleService:
    """Compatibility facade for version endpoints under `/automations`."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.adapters = build_catalog_adapters(db)

    def list_sources(self, automation_id: int) -> list:
        return self.adapters.catalog.list_sources(automation_id)

    def list_versions(self, automation_id: int) -> list:
        return ListAutomationVersions(self.adapters.catalog).execute(automation_id)

    def activate(self, automation_id: int, version_id: int, user: User):
        try:
            return PublishAutomationVersion(
                self.adapters.catalog,
                self.adapters.audit,
                self.adapters.outbox,
                self.adapters.transaction,
            ).execute(automation_id, version_id, _actor(user))
        except CatalogValidationError as exc:
            raise ValueError(str(exc)) from exc

    def deprecate(self, automation_id: int, version_id: int, user: User):
        try:
            return DeprecateAutomationVersion(
                self.adapters.catalog,
                self.adapters.audit,
                self.adapters.outbox,
                self.adapters.transaction,
            ).execute(automation_id, version_id, _actor(user))
        except CatalogValidationError as exc:
            raise ValueError(str(exc)) from exc

    def check_for_update(self, automation_id: int) -> dict:
        source = self.adapters.catalog.get_active_source(automation_id)
        if source is None or source.type != "github":
            raise ValueError("Esta automacao nao possui uma origem GitHub configurada.")

        from app.integrations.github.client import GithubAppClient, GithubAppNotConfiguredError

        try:
            client = GithubAppClient()
        except GithubAppNotConfiguredError as exc:
            raise ValueError(str(exc)) from exc

        latest_commit = client.get_latest_commit_for_path(
            source.integration_id,
            source.owner,
            source.repository,
            source.branch,
            source.automation_path,
        )
        current_version = self.adapters.catalog.get_latest_published_version(automation_id)
        update_available = bool(latest_commit) and latest_commit != source.last_commit_sha
        self.adapters.catalog.update_source(
            source.id,
            {"sync_status": "update_available" if update_available else "synced"},
        )
        self.db.commit()
        return {
            "update_available": update_available,
            "current_commit": source.last_commit_sha,
            "latest_commit": latest_commit,
            "current_version": current_version.version if current_version else None,
        }


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)
