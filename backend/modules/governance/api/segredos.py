"""API dos segredos usados pelas automações (13/11/2026).

- ``GET /segredos``: lista com campos (valor só dos visíveis), versão, validade, automações que
  usam e último uso (``segredos.ver``).
- ``POST /segredos``: cria com ``campos`` ``[{"nome", "oculto", "valor"}]`` (``segredos.gerenciar``).
- ``PUT /segredos/{id}/campos``: os campos passam a ser os enviados; ``valor`` vazio mantém o
  atual; valor trocado gera versão nova (``segredos.gerenciar``).
- ``PUT /segredos/{id}``: nome, descrição e situação (ativo/desativado) (``segredos.gerenciar``).
- ``PUT /segredos/{id}/automacoes``: quais automações usam este segredo (``segredos.gerenciar``).
- ``GET /segredos/{id}/versoes``: histórico de versões, sem valor (``segredos.ver``).
- ``GET /segredos/da-automacao/{id}``: os segredos que a automação usa (``segredos.ver``).
- ``POST``/``DELETE /segredos/da-automacao/{id}/{segredo_id}``: liga e desliga (``segredos.gerenciar``).

As rotas antigas ``POST /secrets`` e ``POST /secrets/{id}/rotate`` seguem para segredo de um
campo (``valor``). Valor oculto nunca volta por nenhuma rota de gestão.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import precisa
from modules.access.api.dependencies import get_current_user
from modules.governance.application.segredos import SegredoInvalido, SegredoNaoEncontrado, Segredos
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.governance.infrastructure.repositories.sqlalchemy_segredos import SqlAlchemySegredos

router = APIRouter(prefix="/segredos", tags=["governance"])

VER = [Depends(precisa("segredos.ver", "segredos.gerenciar"))]
GERENCIAR = [Depends(precisa("segredos.gerenciar"))]


def segredos(db: Session) -> Segredos:
    adapters = build_governance_adapters(db)
    return Segredos(SqlAlchemySegredos(db), adapters.cipher, adapters.audit)


def _fazer(db: Session, acao: Any) -> Any:
    try:
        resultado = acao()
        db.commit()
        return resultado
    except SegredoNaoEncontrado as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SegredoInvalido as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", dependencies=VER)
def listar(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"segredos": segredos(db).painel()}


@router.post("", status_code=201, dependencies=GERENCIAR)
def criar(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return _fazer(db, lambda: segredos(db).criar(user, corpo))


@router.put("/{segredo_id}/campos", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def mudar_campos(segredo_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                 user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: segredos(db).mudar_campos(user, segredo_id, corpo))


@router.get("/da-automacao/{automation_id}", dependencies=VER)
def da_automacao(automation_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"segredos": _fazer(db, lambda: segredos(db).da_automacao(automation_id))}


@router.post("/da-automacao/{automation_id}/{segredo_id}", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def ligar(automation_id: int, segredo_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: segredos(db).ligar(user, segredo_id, automation_id))


@router.delete("/da-automacao/{automation_id}/{segredo_id}", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def desligar(automation_id: int, segredo_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: segredos(db).desligar(user, segredo_id, automation_id))


@router.get("/{segredo_id}/versoes", dependencies=VER)
def versoes(segredo_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"versoes": _fazer(db, lambda: segredos(db).versoes(segredo_id))}


@router.put("/{segredo_id}/automacoes", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def definir_automacoes(segredo_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                       user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: segredos(db).definir_automacoes(user, segredo_id, corpo.get("automacoes")))


@router.put("/{segredo_id}", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def mudar(segredo_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
          user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: segredos(db).mudar(user, segredo_id, corpo))
