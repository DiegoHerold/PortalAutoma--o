from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import is_admin
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogRead
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/", response_model=list[AuditLogRead])
def get_audit_logs(
    actor: str | None = Query(None, description="Filter by actor email"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    action: str | None = Query(None, description="Filter by action"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit logs. Only accessible to admin users.
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    
    audit_service = AuditService(db)
    audit_logs = audit_service.get_audit_logs(
        actor=actor,
        entity_type=entity_type,
        action=action,
        limit=limit,
        offset=offset,
    )
    
    return [AuditLogRead.from_audit_log(log) for log in audit_logs]
