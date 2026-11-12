from __future__ import annotations

from typing import Any

from fastapi import Depends, status
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.database import get_db
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


def precisa(*chaves: str) -> Any:
    """Dependência de rota: o papel da pessoa inclui alguma destas funcionalidades
    (``historico.ver``, ``usuarios.gerenciar``...). Admin passa sempre."""
    from modules.access.api.dependencies import get_current_user
    from modules.access.infrastructure.adapters import build_access_adapters as _adapters

    def _conferir(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
        access = _adapters(db).access
        checker = PermissionChecker(access)
        if any(checker.has_permission(user, chave) for chave in chaves):
            return
        # Usuário montado só com o nome do papel (sem role_id): as funcionalidades vêm do papel pelo nome.
        papel = getattr(user, "role", None)
        slug = getattr(papel, "slug", papel)
        if getattr(user, "role_id", None) is None and getattr(papel, "id", None) is None and isinstance(slug, str):
            registro = access.get_role_by_slug(slug)
            if registro is not None and set(chaves) & set(access.list_permissions_for_role(registro.id)):
                return
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", "O seu papel não inclui esta área do Portal.")

    return _conferir


def acesso_por_automacao(db: Session) -> Any:
    from modules.access.application.concessoes import AcessoPorAutomacao
    from modules.access.infrastructure.repositories.sqlalchemy_grants import SqlAlchemyGrantRepository

    return AcessoPorAutomacao(build_access_adapters(db).access, SqlAlchemyGrantRepository(db))


def ensure_automation_grant(db: Session, user: Any, automation_id: int | None, acao: str) -> None:
    """Concessão por automação (Fase 4): ``ver_execucoes``, ``ver_telas_e_logs``, ``executar``..."""
    try:
        acesso_por_automacao(db).garantir(user, automation_id, acao)
    except AccessResourceNotFound as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc


def ensure_permission(db: Session, user: Any, permission: str) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_permission(user, permission)
    except AuthorizationDenied as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc)) from exc
