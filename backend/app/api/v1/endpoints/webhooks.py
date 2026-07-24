from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import asyncio
import time
from collections import defaultdict

from app.core.config import get_settings
from app.core.database import get_db
from app.domain.trigger_mapping import apply_parameter_mapping
from app.integrations.github.client import verify_webhook_signature
from app.models.trigger import Trigger
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_source_repository import AutomationSourceRepository
from app.repositories.github_integration_repository import GithubIntegrationRepository
from app.repositories.trigger_repository import TriggerRepository
from app.schemas.job import JobCreate
from app.services.job_dispatcher_service import JobDispatcherService
from app.services.audit_service import AuditService

router = APIRouter()

# Simple in-memory rate limiter
rate_limiter = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100


def check_rate_limit(client_ip: str) -> bool:
    """Simple rate limiting: max 100 requests per minute per IP."""
    now = time.time()
    
    # Clean old entries
    rate_limiter[client_ip] = [
        timestamp for timestamp in rate_limiter[client_ip]
        if now - timestamp < RATE_LIMIT_WINDOW
    ]
    
    # Check limit
    if len(rate_limiter[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    # Add current request
    rate_limiter[client_ip].append(now)
    return True


@router.post("/trigger/{route_path:path}")
async def webhook_trigger(
    route_path: str,
    request: Request,
    x_forwarded_for: str | None = Header(None),
    x_webhook_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint for triggering automations (e.g. from N8N).

    Preferred: send the trigger's secret in the `X-Webhook-Secret` header --
    it never ends up in access logs or gets echoed back in a redirect.
    `?secret=` (query string) and `secret_token` (body) are still accepted
    for backward compatibility with triggers configured before this header
    existed, but new integrations should use the header.

    If the trigger has a parameter_mapping configured, the automation
    receives only the mapped parameters. Otherwise it receives the raw
    payload shape (`webhook_data`/`headers`/`query_params`), same as before.
    """
    # Get client IP for rate limiting
    client_ip = x_forwarded_for or request.client.host

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Get request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    headers = dict(request.headers)
    query_params = dict(request.query_params)
    secret_token = x_webhook_secret or query_params.get("secret") or body.get("secret_token")

    if not secret_token:
        raise HTTPException(status_code=400, detail="Missing secret token (envie no header X-Webhook-Secret)")

    # Find trigger by route path and validate secret
    trigger_repo = TriggerRepository(db)
    trigger = trigger_repo.get_by_route_path_normalized(route_path)

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    if not trigger.is_active:
        raise HTTPException(status_code=404, detail="Trigger not active")

    if trigger.secret_token != secret_token:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    try:
        automation = AutomationRepository(db).get(trigger.automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found")

        payload_json = apply_parameter_mapping(trigger.parameter_mapping_json, body, headers, query_params)

        job_payload = JobCreate(
            automation_id=trigger.automation_id,
            priority=automation.default_priority,
            payload_json=payload_json,
        )

        # Dispatch job
        dispatcher = JobDispatcherService(db)
        job = dispatcher.dispatch_system(job_payload, trigger_id=trigger.id)

        # Audit the trigger
        audit_service = AuditService(db)
        audit_service.record(
            action="webhook_triggered",
            actor_email=None,
            actor_type="trigger",
            entity_type="job",
            entity_id=str(job.id),
            details=f"Triggered by webhook {route_path} (trigger {trigger.id})",
        )

        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "job_id": job.id,
                "message": "Automation triggered successfully"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        # Audit the failed trigger
        audit_service = AuditService(db)
        audit_service.record(
            action="webhook_trigger_failed",
            actor_email=None,
            actor_type="trigger",
            entity_type="trigger",
            entity_id=str(trigger.id),
            details=f"Failed to trigger webhook {route_path}: {str(e)}",
        )

        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to trigger automation: {str(e)}")


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Receives GitHub App webhook events (push, installation,
    installation_repositories). Marks affected AutomationSource rows as
    "update_available" so the UI can prompt a re-import — it never triggers
    an automatic re-import (an operator must review and confirm, same as any
    other import), matching the task's "sem execução automática" rule.
    """
    settings = get_settings()
    raw_body = await request.body()

    if settings.github_app_webhook_secret:
        if not verify_webhook_signature(raw_body, x_hub_signature_256, settings.github_app_webhook_secret):
            raise HTTPException(status_code=401, detail="Assinatura de webhook inválida.")

    payload = await request.json()
    source_repo = AutomationSourceRepository(db)
    integrations = GithubIntegrationRepository(db)

    if x_github_event == "installation":
        action = payload.get("action")
        installation_id = payload.get("installation", {}).get("id")
        integration = integrations.get_by_installation_id(installation_id) if installation_id else None
        if integration and action == "deleted":
            integrations.delete(integration)
        elif integration and action == "suspend":
            from app.utils.datetime import utcnow

            integration.suspended_at = utcnow()
            integrations.update(integration)
        elif integration and action == "unsuspend":
            integration.suspended_at = None
            integrations.update(integration)
        return JSONResponse(status_code=200, content={"ok": True})

    if x_github_event == "push":
        installation_id = payload.get("installation", {}).get("id")
        repository = payload.get("repository", {})
        owner = repository.get("owner", {}).get("login")
        repo_name = repository.get("name")
        ref = payload.get("ref", "")
        branch = ref.removeprefix("refs/heads/")
        changed_paths: set[str] = set()
        for commit in payload.get("commits", []):
            changed_paths.update(commit.get("added", []))
            changed_paths.update(commit.get("modified", []))
            changed_paths.update(commit.get("removed", []))

        integration = integrations.get_by_installation_id(installation_id) if installation_id else None
        if integration and owner and repo_name:
            affected = source_repo.list_for_integration(integration.id)
            for source in affected:
                if source.owner != owner or source.repository != repo_name or source.branch != branch:
                    continue
                prefix = (source.automation_path or "").rstrip("/") + "/"
                touched = any(p == source.automation_path or p.startswith(prefix) for p in changed_paths)
                if touched:
                    source.sync_status = "update_available"
                    source_repo.update(source)
        db.commit()
        return JSONResponse(status_code=200, content={"ok": True})

    # installation_repositories and any other event types: acknowledge only.
    return JSONResponse(status_code=200, content={"ok": True, "ignored_event": x_github_event})