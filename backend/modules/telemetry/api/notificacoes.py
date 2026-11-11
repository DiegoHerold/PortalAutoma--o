"""Notificações (Fase 6): os avisos de cada pessoa e o que ela escolhe receber.

- ``GET /notificacoes``: os avisos da pessoa, do mais novo, e quantos estão por ler.
- ``POST /notificacoes/lidas``: marca como lidos (os indicados, ou todos).
- ``GET`` e ``PUT /notificacoes/preferencias``: o que receber e o tempo da fila parada.
  Máquina offline e fila parada só para administradores e gestores.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.telemetry.domain.notificacoes import (
    FILA_MINUTOS_LIMITES,
    SO_GESTORES,
    TIPOS,
    PreferenciaInvalida,
    validar_preferencia,
)
from modules.telemetry.infrastructure.email_graph import situacao_do_envio
from modules.telemetry.infrastructure.repositories.sqlalchemy_notificacoes import GESTORES, SqlAlchemyNotificacoes

router = APIRouter(tags=["notificacoes"])

ROTULOS = {
    "erro": "Erro numa execução",
    "atencao": "Item aguardando uma pessoa",
    "maquina_offline": "Máquina offline",
    "fila_parada": "Fila parada",
    "termino": "Término de execução",
}


def _gestor(user: Any) -> bool:
    return getattr(getattr(user, "role", None), "slug", None) in GESTORES


class Lidas(BaseModel):
    ids: list[str] | None = Field(default=None, max_length=500)


class Preferencia(BaseModel):
    tipos: list[str] = Field(default_factory=list, max_length=len(TIPOS))
    fila_minutos: int = 30


@router.get("/notificacoes")
def listar(limite: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> dict[str, Any]:
    avisos, nao_lidas = SqlAlchemyNotificacoes(db).do_usuario(int(user.id), limite)
    return {"avisos": avisos, "nao_lidas": nao_lidas}


@router.post("/notificacoes/lidas")
def marcar_lidas(corpo: Lidas, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, int]:
    n = SqlAlchemyNotificacoes(db).marcar_lidas(int(user.id), corpo.ids, datetime.now(UTC))
    db.commit()
    return {"marcadas": n}


def _preferencia(db: Session, user: Any) -> dict[str, Any]:
    tipos, minutos = SqlAlchemyNotificacoes(db).preferencia(int(user.id))
    gestor = _gestor(user)
    return {
        "tipos": tipos, "fila_minutos": minutos, "email": getattr(user, "email", None),
        "disponiveis": [{"tipo": t, "rotulo": ROTULOS[t], "so_gestores": t in SO_GESTORES}
                        for t in TIPOS if gestor or t not in SO_GESTORES],
        "fila_minutos_limites": list(FILA_MINUTOS_LIMITES),
        "envio_por_email": situacao_do_envio(get_settings()),
    }


@router.get("/notificacoes/preferencias")
def ver_preferencia(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return _preferencia(db, user)


@router.put("/notificacoes/preferencias")
def gravar_preferencia(corpo: Preferencia, db: Session = Depends(get_db),
                       user: Any = Depends(get_current_user)) -> dict[str, Any]:
    try:
        tipos, minutos = validar_preferencia(corpo.tipos, corpo.fila_minutos, _gestor(user))
    except PreferenciaInvalida as exc:
        raise http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc)) from exc
    SqlAlchemyNotificacoes(db).gravar_preferencia(int(user.id), list(tipos), minutos)
    db.commit()
    return _preferencia(db, user)
