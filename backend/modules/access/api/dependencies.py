from __future__ import annotations

from typing import Any

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.application.contas_de_servico import e_credencial_de_conta
from modules.access.application.use_cases import AuthenticateToken, PermissionChecker
from modules.access.domain import AuthenticationFailed, AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters


settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> Any:
    adapters = build_access_adapters(db)
    try:
        if e_credencial_de_conta(token):
            # Conta de serviço (13/11/2026): o usuário técnico dela, com papel e times.
            usuario = contas_de_servico(db).autenticar(
                token, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
            db.commit()  # último uso (e nada mais está pendente neste ponto)
            return usuario
        return AuthenticateToken(adapters.access, adapters.tokens).execute(token)
    except AuthenticationFailed as exc:
        db.commit()  # a recusa fica na auditoria
        raise http_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Could not validate credentials.",
        ) from exc
    except (JWTError, ValueError) as exc:
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



def contas_de_servico(db: Session) -> Any:
    from modules.access.application.contas_de_servico import ContasDeServico
    from modules.access.infrastructure.repositories.sqlalchemy_contas_de_servico import SqlAlchemyContasDeServico
    from modules.access.infrastructure.repositories.sqlalchemy_times import SqlAlchemyTimes
    from modules.governance.infrastructure.adapters import build_governance_adapters

    return ContasDeServico(build_access_adapters(db).access, SqlAlchemyContasDeServico(db), SqlAlchemyTimes(db),
                           build_governance_adapters(db).audit)
