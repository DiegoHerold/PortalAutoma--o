from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from modules.catalog.domain.errors import ImmutablePublishedVersionError, InvalidCatalogStateTransition
from modules.catalog.domain.states import ALLOWED_AUTOMATION_VERSION_TRANSITIONS, AutomationVersionStatus
from modules.catalog.domain.value_objects import SemVer


@dataclass(frozen=True)
class AutomationVersion:
    id: str
    automation_id: str
    version: str
    status: AutomationVersionStatus = AutomationVersionStatus.DRAFT
    manifest_id: str | None = None
    package_id: str | None = None
    runtime_version_id: str | None = None
    release_notes: str | None = None
    source_repository: str | None = None
    source_branch: str | None = None
    source_tag: str | None = None
    source_commit_sha: str | None = None
    build_id: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    published_by: str | None = None
    published_at: datetime | None = None
    deprecated_at: datetime | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        SemVer(self.version)
        if self.status == AutomationVersionStatus.PUBLISHED:
            missing = [
                name
                for name, value in {
                    "manifest_id": self.manifest_id,
                    "package_id": self.package_id,
                    "runtime_version_id": self.runtime_version_id,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"Published automation versions require: {', '.join(missing)}.")

    @property
    def is_immutable(self) -> bool:
        return self.status in {
            AutomationVersionStatus.PUBLISHED,
            AutomationVersionStatus.DEPRECATED,
            AutomationVersionStatus.BLOCKED,
        }

    def transition_to(self, status: AutomationVersionStatus) -> "AutomationVersion":
        if status not in ALLOWED_AUTOMATION_VERSION_TRANSITIONS[self.status]:
            raise InvalidCatalogStateTransition(f"Cannot transition automation version from {self.status} to {status}.")
        now = datetime.now(UTC)
        return AutomationVersion(
            id=self.id,
            automation_id=self.automation_id,
            version=self.version,
            status=status,
            manifest_id=self.manifest_id,
            package_id=self.package_id,
            runtime_version_id=self.runtime_version_id,
            release_notes=self.release_notes,
            source_repository=self.source_repository,
            source_branch=self.source_branch,
            source_tag=self.source_tag,
            source_commit_sha=self.source_commit_sha,
            build_id=self.build_id,
            created_by=self.created_by,
            created_at=self.created_at,
            published_by=self.published_by,
            published_at=now if status == AutomationVersionStatus.PUBLISHED else self.published_at,
            deprecated_at=now if status == AutomationVersionStatus.DEPRECATED else self.deprecated_at,
            blocked_at=now if status == AutomationVersionStatus.BLOCKED else self.blocked_at,
        )

    def ensure_mutable(self) -> None:
        if self.is_immutable:
            raise ImmutablePublishedVersionError("Published, deprecated and blocked versions are immutable.")
