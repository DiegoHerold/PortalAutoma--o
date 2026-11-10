"""API das concessões por automação: quem pode ver execuções, telas e logs, executar..."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import acesso_por_automacao
from modules.access.api.dependencies import get_current_user
from modules.access.application.concessoes import GerenciarConcessoes
from modules.access.domain import AccessResourceNotFound, AuthorizationDenied
from modules.access.domain.concessao import ACOES, AcaoInvalida
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.repositories.sqlalchemy_grants import SqlAlchemyGrantRepository

router = APIRouter(prefix="/automations/{automation_id}/acessos", tags=["access"])


def _gerenciar(db: Session) -> GerenciarConcessoes:
    adapters = build_access_adapters(db)
    return GerenciarConcessoes(adapters.access, SqlAlchemyGrantRepository(db), adapters.audit, adapters.transaction)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, AccessResourceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AuthorizationDenied):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("")
def listar(automation_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"acoes_possiveis": list(ACOES), "concessoes": _gerenciar(db).listar(user, automation_id)}
    except (AccessResourceNotFound, AuthorizationDenied) as exc:
        raise _http(exc) from exc


@router.put("")
def definir(automation_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
            user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``{"user_id": 7, "acoes": ["ver_telas_e_logs"]}`` ou ``{"team_id": 2, ...}``. Lista vazia retira."""
    acoes = corpo.get("acoes")
    if not isinstance(acoes, list) or not all(isinstance(a, str) for a in acoes):
        raise HTTPException(status_code=422, detail="acoes deve ser uma lista de textos.")
    try:
        concessao = _gerenciar(db).definir(
            user, automation_id, user_id=_inteiro(corpo.get("user_id")), team_id=_inteiro(corpo.get("team_id")),
            acoes=acoes, agora=datetime.now(UTC))
    except (AccessResourceNotFound, AuthorizationDenied, AcaoInvalida) as exc:
        db.rollback()
        raise _http(exc) from exc
    return {"concessao": concessao}


@router.get("/minhas")
def minhas(automation_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """O que o usuário atual pode nesta automação: a tela mostra ou esconde telas e logs por isto."""
    acesso = acesso_por_automacao(db)
    if build_access_adapters(db).access.get_automation_category_id(automation_id) is None:
        raise HTTPException(status_code=404, detail="Automação não encontrada.")
    return {"acoes": [a for a in ACOES if acesso.pode(user, automation_id, a)]}


def _inteiro(valor: Any) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise HTTPException(status_code=422, detail="user_id e team_id são números.")
    return valor
