"""API das contas de serviço (13/11/2026).

- ``GET /contas-de-servico``: ``contas_de_servico.ver``.
- ``POST /contas-de-servico``: cria e devolve a credencial **uma única vez**.
- ``PUT /contas-de-servico/{id}``: nome, descrição, papel, times, validade, situação.
- ``POST /contas-de-servico/{id}/credencial``: gera uma nova (a anterior para na hora).
- ``DELETE /contas-de-servico/{id}``: apaga a conta e o usuário técnico.

Mudanças pedem ``contas_de_servico.gerenciar``. Respostas com credencial não vão para cache.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import contas_de_servico, get_current_user
from modules.access.application.contas_de_servico import ContaInvalida
from modules.access.domain import AccessResourceNotFound, AuthorizationDenied

router = APIRouter(prefix="/contas-de-servico", tags=["access"])

SEM_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _fazer(db: Session, acao: Any) -> Any:
    try:
        resultado = acao()
        db.commit()
        return resultado
    except AuthorizationDenied as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AccessResourceNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContaInvalida as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A conta já tem registros ligados a ela (execuções pedidas, por "
                                                    "exemplo). Desative em vez de apagar.") from exc


@router.get("")
def listar(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"contas": _fazer(db, lambda: contas_de_servico(db).listar(user))}


@router.post("", status_code=201)
def criar(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    criada = _fazer(db, lambda: contas_de_servico(db).criar(user, corpo))
    return JSONResponse(status_code=201, content=jsonable_encoder(criada), headers=SEM_CACHE)


@router.put("/{conta_id}")
def mudar(conta_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
          user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"conta": _fazer(db, lambda: contas_de_servico(db).mudar(user, conta_id, corpo))}


@router.post("/{conta_id}/credencial")
def gerar_credencial(conta_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    gerada = _fazer(db, lambda: contas_de_servico(db).gerar_credencial(user, conta_id))
    return JSONResponse(content=jsonable_encoder(gerada), headers=SEM_CACHE)


@router.delete("/{conta_id}", status_code=204, response_model=None, response_class=Response)
def apagar(conta_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: contas_de_servico(db).apagar(user, conta_id))
