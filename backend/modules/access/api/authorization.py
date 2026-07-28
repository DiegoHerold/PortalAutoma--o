from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from api.errors import http_error
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AccessResourceNotFound, AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters


def ensure_automation_action(db: Session, user: Any, automation_id: int, action: str) -> int:
    try:
        return PermissionChecker(build_access_adapters(db).access).ensure_automation_action(user, automation_id, action)
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


def ensure_permission(db: Session, user: Any, permission: str) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_permission(user, permission)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
