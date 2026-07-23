from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.constants import AutomationVersionStatus
from app.models.automation_version import AutomationVersion
from app.models.user import User
from app.repositories.automation_source_repository import AutomationSourceRepository
from app.repositories.automation_version_repository import AutomationVersionRepository
from app.services.audit_service import AuditService
from app.utils.datetime import utcnow


class AutomationVersionLifecycleService:
    """
    Version states (see docs/automation-catalog.md): validating -> ready ->
    published -> deprecated/disabled. Only one version per automation is
    `published` at a time — activating a new one automatically deprecates
    whichever was published before it. This is what `AutomationPackageResolver`
    reads at dispatch time.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.versions = AutomationVersionRepository(db)
        self.sources = AutomationSourceRepository(db)
        self.audit = AuditService(db)

    def list_sources(self, automation_id: int) -> list:
        return self._all_sources_for_automation(automation_id)

    def _all_sources_for_automation(self, automation_id: int):
        from sqlalchemy import select

        from app.models.automation_source import AutomationSource

        return list(
            self.db.scalars(
                select(AutomationSource)
                .where(AutomationSource.automation_id == automation_id)
                .order_by(AutomationSource.created_at.desc())
            ).all()
        )

    def list_versions(self, automation_id: int) -> list[AutomationVersion]:
        return self.versions.list_for_automation(automation_id)

    def _get_owned_version(self, automation_id: int, version_id: int) -> AutomationVersion:
        version = self.versions.get(version_id)
        if version is None or version.automation_id != automation_id:
            raise ValueError("Versão não encontrada para esta automação.")
        return version

    def activate(self, automation_id: int, version_id: int, user: User) -> AutomationVersion:
        version = self._get_owned_version(automation_id, version_id)
        if version.status not in {AutomationVersionStatus.READY, AutomationVersionStatus.DEPRECATED}:
            raise ValueError(f"Versão em estado '{version.status}' não pode ser ativada.")

        for other in self.versions.list_for_automation(automation_id):
            if other.id != version.id and other.status == AutomationVersionStatus.PUBLISHED:
                other.status = AutomationVersionStatus.DEPRECATED
                self.versions.update(other)

        version.status = AutomationVersionStatus.PUBLISHED
        version.published_at = utcnow()
        self.versions.update(version)

        self.audit.record(
            "automation_version_activated",
            actor_email=user.email,
            entity_type="automation_version",
            entity_id=str(version.id),
            details=f"automation_id={automation_id} version={version.version}",
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def deprecate(self, automation_id: int, version_id: int, user: User) -> AutomationVersion:
        version = self._get_owned_version(automation_id, version_id)
        if version.status != AutomationVersionStatus.PUBLISHED:
            raise ValueError("Apenas uma versão publicada pode ser depreciada.")
        version.status = AutomationVersionStatus.DEPRECATED
        self.versions.update(version)
        self.audit.record(
            "automation_version_deprecated",
            actor_email=user.email,
            entity_type="automation_version",
            entity_id=str(version.id),
            details=f"automation_id={automation_id} version={version.version}",
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def check_for_update(self, automation_id: int) -> dict:
        source = self.sources.get_active_for_automation(automation_id)
        if source is None or source.type != "github":
            raise ValueError("Esta automação não possui uma origem GitHub configurada.")

        from app.integrations.github.client import GithubAppClient, GithubAppNotConfiguredError

        try:
            client = GithubAppClient()
        except GithubAppNotConfiguredError as exc:
            raise ValueError(str(exc)) from exc

        latest_commit = client.get_latest_commit_for_path(
            source.integration_id, source.owner, source.repository, source.branch, source.automation_path
        )

        current_version = self.versions.get_latest_published(automation_id)
        update_available = bool(latest_commit) and latest_commit != source.last_commit_sha
        source.sync_status = "update_available" if update_available else "synced"
        self.sources.update(source)
        self.db.commit()

        return {
            "update_available": update_available,
            "current_commit": source.last_commit_sha,
            "latest_commit": latest_commit,
            "current_version": current_version.version if current_version else None,
        }
