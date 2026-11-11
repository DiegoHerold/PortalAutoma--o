"""API dos times: membros, times de uma pessoa e permissões (por categoria aqui; por automação,
nas concessões de cada automação, ``/automations/{id}/acessos`` com ``team_id``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.application.times import GerenciarTimes
from modules.access.domain import AccessResourceNotFound, AuthorizationDenied
from modules.access.domain.concessao import ACOES
from modules.access.domain.times import TimeInvalido
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.repositories.sqlalchemy_times import SqlAlchemyTimes

router = APIRouter(tags=["access"])


def _times(db: Session) -> GerenciarTimes:
    adapters = build_access_adapters(db)
    return GerenciarTimes(adapters.access, SqlAlchemyTimes(db), adapters.audit, adapters.transaction)


def _chamar(db: Session, acao: Any) -> Any:
    try:
        return acao()
    except AccessResourceNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthorizationDenied as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeInvalido as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/teams/{team_id}/detalhes")
def detalhes(team_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Membros, permissões por categoria e por automação, e as ações que uma automação aceita."""
    return {**_chamar(db, lambda: _times(db).ver(user, team_id)), "acoes_possiveis": list(ACOES)}


@router.post("/teams/{team_id}/membros")
def adicionar(team_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
              user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``{"usuarios": [3, 7]}``: quem já é membro fica como está."""
    return {"membros": _chamar(db, lambda: _times(db).adicionar_membros(user, team_id, corpo.get("usuarios")))}


@router.delete("/teams/{team_id}/membros/{user_id}")
def remover(team_id: int, user_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"membros": _chamar(db, lambda: _times(db).remover_membro(user, team_id, user_id))}


@router.put("/teams/{team_id}/categorias")
def categorias(team_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
               user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``{"categorias": [{"category_id": 3, "can_view": true, "can_execute": true}]}``: substitui as do time."""
    return {"categorias": _chamar(db, lambda: _times(db).definir_categorias(user, team_id, corpo.get("categorias")))}


@router.get("/users/{user_id}/times")
def times_do_usuario(user_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"times": _chamar(db, lambda: _times(db).times_do_usuario(user, user_id))}


@router.put("/users/{user_id}/times")
def definir_times(user_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                  user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``{"times": [1, 4]}``: a pessoa passa a estar exatamente nesses times."""
    return {"times": _chamar(db, lambda: _times(db).definir_times_do_usuario(user, user_id, corpo.get("times")))}
