from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.automation import Automation
from app.repositories.automation_version_repository import AutomationVersionRepository


def resolve_package_for_dispatch(db: Session, automation: Automation) -> tuple[str | None, str | None]:
    """
    Where the Agent gateway gets the download URL + hash for a dispatched job.

    Preference order:
    1. The automation's `published` AutomationVersion from the catalog (GitHub
       import or manual ZIP upload) — a fresh, short-lived download URL is
       minted here, at dispatch time, so it's still valid when the Agent
       actually downloads it (unlike a URL baked in at activation time).
    2. The automation's legacy static `package_url`/`package_sha256` columns,
       for automations created directly (outside the catalog) before this
       feature existed — keeps existing behavior 100% backward compatible.
    """
    from app.integrations.storage.factory import get_package_storage

    version = AutomationVersionRepository(db).get_latest_published(automation.id)
    if version is not None:
        storage = get_package_storage()
        url = storage.get_download_url(
            version.artifact_bucket, version.artifact_object_key, expires_in_seconds=600
        )
        return url, version.artifact_sha256
    return automation.package_url, automation.package_sha256
