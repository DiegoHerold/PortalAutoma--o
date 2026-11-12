"""API dos papéis globais (12/11/2026).

- ``GET /papeis``, ``GET /papeis/funcionalidades``: quem tem a funcionalidade Papéis vê.
- ``POST /papeis``, ``PUT /papeis/{id}``, ``DELETE /papeis/{id}?substituto=``: só administradores.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.application.papeis import ADMIN, Papeis, PapelNaoEncontrado
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain.funcionalidades import FuncionalidadeInvalida as PapelInvalido
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.repositories.sqlalchemy_papeis import SqlAlchemyPapeis

router = APIRouter(prefix="/papeis", tags=["access"])


class _Transacao:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()


def _papeis(db: Session) -> Papeis:
    from modules.governance.infrastructure.adapters import build_governance_adapters

    return Papeis(SqlAlchemyPapeis(db), build_governance_adapters(db).audit, _Transacao(db))


def _slug(user: Any) -> str | None:
    papel = getattr(user, "role", None)
    return getattr(papel, "slug", papel)


def _ver(db: Session, user: Any) -> None:
    if _slug(user) != ADMIN and not PermissionChecker(build_access_adapters(db).access).has_permission(user, "papeis.ver"):
        raise HTTPException(status_code=403, detail="Sem permissão para ver os papéis.")


def _admin(user: Any) -> None:
    if _slug(user) != ADMIN:
        raise HTTPException(status_code=403, detail="Só administradores mudam os papéis.")


def _executar(db: Session, acao: Any) -> Any:
    try:
        return acao()
    except PapelNaoEncontrado as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PapelInvalido as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def listar(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ver(db, user)
    return {"papeis": _papeis(db).listar(), "pode_editar": _slug(user) == ADMIN}


@router.get("/funcionalidades")
def funcionalidades(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ver(db, user)
    return {"funcionalidades": _papeis(db).funcionalidades()}


@router.post("", status_code=201)
def criar(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _admin(user)
    base = corpo.get("baseado_em")
    return _executar(db, lambda: _papeis(db).criar(
        str(user.id), nome=corpo.get("nome"), descricao=corpo.get("descricao"),
        funcionalidades=_tabela(corpo.get("funcionalidades")), baseado_em=int(base) if base not in (None, "") else None))


@router.put("/{papel_id}")
def alterar(papel_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
            user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _admin(user)
    return _executar(db, lambda: _papeis(db).alterar(
        str(user.id), papel_id, nome=corpo.get("nome"), descricao=corpo.get("descricao"),
        funcionalidades=_tabela(corpo.get("funcionalidades"))))


@router.delete("/{papel_id}")
def apagar(papel_id: int, substituto: int | None = Query(default=None), db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _admin(user)
    return _executar(db, lambda: _papeis(db).apagar(str(user.id), papel_id, substituto=substituto))


def _tabela(valor: Any) -> dict[str, str | None] | None:
    if valor is None:
        return None
    if not isinstance(valor, dict) or not all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in valor.items()):
        raise HTTPException(status_code=422, detail='funcionalidades: {"historico": "ver", "usuarios": "gerenciar", ...}')
    return valor
