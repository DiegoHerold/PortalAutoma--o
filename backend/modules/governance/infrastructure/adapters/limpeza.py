"""Quem apaga cada regra de limpeza: chave do catálogo -> função do contexto dono da tabela.

Toda regra editável do catálogo (``governance/domain/configuracoes.py``) precisa estar aqui;
``tests`` confere. Cada função tem a forma ``(db, corte, lote) -> quantos saíram``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from modules.dispatch.infrastructure import limpeza as dispatch
from modules.fleet.infrastructure import limpeza as fleet
from modules.orchestration.infrastructure import limpeza as orchestration
from modules.shared.infrastructure import limpeza as shared
from modules.telemetry.infrastructure import limpeza as telemetry

Limpador = Callable[[Session, datetime, int], int]

LIMPADORES: dict[str, Limpador] = {
    "notificacoes": telemetry.notificacoes,
    "maquinas.recursos": fleet.recursos,
    "maquinas.sessoes": fleet.sessoes,
    "maquinas.comandos": dispatch.comandos,
    "maquinas.diagnosticos": fleet.diagnosticos,
    "acesso.sessoes_diretas": fleet.sessoes_diretas,
    "acesso.tokens_de_job": dispatch.tokens_de_job,
    "acesso.codigos_vencidos": fleet.codigos_vencidos,
    "interno.mensagens": telemetry.mensagens,
    "interno.idempotencia": shared.idempotencia,
    "execucoes.decisoes": dispatch.decisoes,
    "execucoes.reconciliacoes": dispatch.reconciliacoes,
    "execucoes.webhooks": orchestration.chamadas_de_webhook,
}


def build_aplicar_limpeza(db: Session):
    from modules.governance.application.configuracoes import AplicarLimpezaDoSistema
    from modules.governance.infrastructure.adapters.factory import build_governance_adapters
    from modules.governance.infrastructure.repositories.sqlalchemy_configuracoes import SqlAlchemyConfiguracoes

    g = build_governance_adapters(db)
    ligados = {chave: (lambda corte, lote, f=funcao: f(db, corte, lote)) for chave, funcao in LIMPADORES.items()}
    return AplicarLimpezaDoSistema(SqlAlchemyConfiguracoes(db), ligados, g.audit, g.transaction)
