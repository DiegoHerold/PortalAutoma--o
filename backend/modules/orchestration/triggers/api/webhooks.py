from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from infrastructure.github.client import verify_webhook_signature
from modules.catalog.infrastructure.orm.models import CatalogAutomationSourceRecord, GithubIntegrationRecord

router = APIRouter(prefix="/webhooks")

_rate_limiter: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 100


# POST /webhooks/trigger/... saiu em 13/11/2026: ver modules/orchestration/webhooks (resposta 410 em antigos.py).


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    raw_body = await request.body()
    if settings.github_app_webhook_secret:
        if not verify_webhook_signature(raw_body, x_hub_signature_256, settings.github_app_webhook_secret):
            raise HTTPException(status_code=401, detail="Assinatura de webhook invalida.")

    payload = await request.json()
    if x_github_event == "installation":
        _handle_installation_event(db, payload)
        db.commit()
        return JSONResponse(status_code=200, content={"ok": True})

    if x_github_event == "push":
        _handle_push_event(db, payload)
        db.commit()
        return JSONResponse(status_code=200, content={"ok": True})

    return JSONResponse(status_code=200, content={"ok": True, "ignored_event": x_github_event})


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    _rate_limiter[client_ip] = [timestamp for timestamp in _rate_limiter[client_ip] if now - timestamp < _RATE_LIMIT_WINDOW_SECONDS]
    if len(_rate_limiter[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
        return False
    _rate_limiter[client_ip].append(now)
    return True


def _handle_installation_event(db: Session, payload: dict[str, Any]) -> None:
    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")
    integration = _get_github_integration(db, installation_id)
    if integration and action == "deleted":
        db.delete(integration)
    elif integration and action == "suspend":
        integration.suspended_at = datetime.now(UTC)
        db.add(integration)
    elif integration and action == "unsuspend":
        integration.suspended_at = None
        db.add(integration)


def _handle_push_event(db: Session, payload: dict[str, Any]) -> None:
    installation_id = payload.get("installation", {}).get("id")
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login")
    repo_name = repository.get("name")
    branch = str(payload.get("ref", "")).removeprefix("refs/heads/")
    integration = _get_github_integration(db, installation_id)
    if not integration or not owner or not repo_name:
        return

    changed_paths: set[str] = set()
    for commit in payload.get("commits", []):
        changed_paths.update(commit.get("added", []))
        changed_paths.update(commit.get("modified", []))
        changed_paths.update(commit.get("removed", []))

    sources = db.scalars(
        select(CatalogAutomationSourceRecord).where(CatalogAutomationSourceRecord.integration_id == integration.id)
    ).all()
    for source in sources:
        if source.owner != owner or source.repository != repo_name or source.branch != branch:
            continue
        prefix = (source.automation_path or "").rstrip("/") + "/"
        touched = any(path == source.automation_path or path.startswith(prefix) for path in changed_paths)
        if touched:
            source.sync_status = "update_available"
            db.add(source)


def _get_github_integration(db: Session, installation_id: int | None) -> GithubIntegrationRecord | None:
    if installation_id is None:
        return None
    return db.scalar(select(GithubIntegrationRecord).where(GithubIntegrationRecord.installation_id == int(installation_id)))
