from __future__ import annotations

from typing import Any

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.application.use_cases import AuthenticateToken, PermissionChecker
from modules.access.domain import AuthenticationFailed, AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters


settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> Any:
    adapters = build_access_adapters(db)
    try:
        return AuthenticateToken(adapters.access, adapters.tokens).execute(token)
    except (AuthenticationFailed, JWTError, ValueError) as exc:
        raise http_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Could not validate credentials.",
        ) from exc


def require_permission(user: Any, permission: str, db: Session, *, category_id: int | None = None) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_permission(user, permission, category_id=category_id)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc

