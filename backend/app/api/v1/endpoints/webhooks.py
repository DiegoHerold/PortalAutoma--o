from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import asyncio
import time
from collections import defaultdict

from app.core.database import get_db
from app.models.trigger import Trigger
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
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint for triggering automations.
    
    Validates secret_token from the trigger configuration.
    Supports n8n webhooks and other HTTP-based triggers.
    """
    # Get client IP for rate limiting
    client_ip = x_forwarded_for or request.client.host
    
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Get request body
    try:
        body = await request.json()
    except:
        body = {}
    
    # Extract secret token from query params or body
    query_params = dict(request.query_params)
    secret_token = query_params.get("secret") or body.get("secret_token")
    
    if not secret_token:
        raise HTTPException(status_code=400, detail="Missing secret token")
    
    # Find trigger by route path and validate secret
    trigger_repo = TriggerRepository(db)
    trigger = trigger_repo.get_by_route_path(f"/{route_path}")
    
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    
    if not trigger.is_active:
        raise HTTPException(status_code=404, detail="Trigger not active")
    
    # Validate secret token
    trigger_config = trigger.config_json or {}
    if trigger_config.get("secret_token") != secret_token:
        raise HTTPException(status_code=401, detail="Invalid secret token")
    
    try:
        # Create job payload
        job_payload = JobCreate(
            automation_id=trigger.automation_id,
            priority=trigger_config.get("priority", "normal"),
            payload_json={
                "webhook_data": body,
                "headers": dict(request.headers),
                "query_params": query_params,
                "trigger_id": trigger.id,
            }
        )
        
        # Dispatch job
        dispatcher = JobDispatcherService(db)
        job = dispatcher.dispatch_system(job_payload)
        
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