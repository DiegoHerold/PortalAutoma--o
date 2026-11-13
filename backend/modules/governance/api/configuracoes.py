"""Configurações do sistema: limites (Governança > Limites) e limpeza automática (Governança > Retenção).

O catálogo em ``domain/configuracoes.py`` diz o que existe; aqui só se lê e se muda o valor.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.governance.api.routes import _ensure
from modules.governance.application.configuracoes import (
    DefinirLimite,
    DefinirPrazoDeLimpeza,
    ListarLimites,
    ListarLimpezas,
)
from modules.governance.domain.configuracoes import LIMITES, ConfiguracaoInvalida
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.governance.infrastructure.limites import esquecer_cache
from modules.governance.infrastructure.repositories.sqlalchemy_configuracoes import SqlAlchemyConfiguracoes

router = APIRouter(tags=["configuracoes"])


class NovoValor(BaseModel):
    valor: int


class NovoPrazo(BaseModel):
    dias: int | None = None
    voltar_ao_padrao: bool = False


def _grupos(itens: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(item["grupo"] for item in itens))


def _valores_de_arquivo() -> dict[str, int]:
    settings = get_settings()
    return {item.chave: int(getattr(settings, (item.variavel_de_ambiente or "").lower(), item.padrao))
            for item in LIMITES if item.origem == "arquivo"}


@router.get("/governance/limites")
def listar_limites(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "limites.ver")
    itens = ListarLimites(SqlAlchemyConfiguracoes(db)).execute(_valores_de_arquivo())
    return {"grupos": _grupos(itens), "itens": itens}


@router.put("/governance/limites/{chave}")
def definir_limite(chave: str, corpo: NovoValor, db: Session = Depends(get_db),
                   user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "limites.gerenciar")
    g = build_governance_adapters(db)
    try:
        DefinirLimite(SqlAlchemyConfiguracoes(db), g.audit, g.transaction).execute(user, chave, corpo.valor)
    except ConfiguracaoInvalida as exc:
        raise http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc)) from exc
    esquecer_cache()
    itens = ListarLimites(SqlAlchemyConfiguracoes(db)).execute(_valores_de_arquivo())
    return next(item for item in itens if item["chave"] == chave)


@router.get("/governance/limpeza")
def listar_limpeza(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "retencao.ver")
    itens = ListarLimpezas(SqlAlchemyConfiguracoes(db)).execute()
    return {"grupos": _grupos(itens), "itens": itens}


@router.put("/governance/limpeza/{chave}")
def definir_prazo(chave: str, corpo: NovoPrazo, db: Session = Depends(get_db),
                  user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "retencao.gerenciar")
    g = build_governance_adapters(db)
    try:
        DefinirPrazoDeLimpeza(SqlAlchemyConfiguracoes(db), g.audit, g.transaction).execute(
            user, chave, corpo.dias, corpo.voltar_ao_padrao)
    except ConfiguracaoInvalida as exc:
        raise http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc)) from exc
    itens = ListarLimpezas(SqlAlchemyConfiguracoes(db)).execute()
    return next(item for item in itens if item["chave"] == chave)
