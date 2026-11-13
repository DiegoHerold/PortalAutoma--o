"""Casos de uso das configurações do sistema: limites e limpeza automática.

O catálogo (``domain/configuracoes.py``) diz o que existe e o padrão; o repositório guarda só
o que alguém mudou. Toda mudança e toda limpeza que apagou algo entram na auditoria.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent
from modules.governance.domain.configuracoes import (
    LIMITES,
    LIMPEZAS,
    corte,
    limite,
    limpeza,
    validar_limite,
    validar_prazo,
)

log = logging.getLogger(__name__)

LOTE = 5000


@dataclass(frozen=True)
class PrazoGravado:
    personalizado: bool
    dias: int | None
    atualizado_por: str | None = None
    atualizado_em: datetime | None = None
    ultima_limpeza_em: datetime | None = None
    ultima_limpeza_apagados: int | None = None
    total_apagados: int = 0


def dias_em_vigor(chave: str, gravado: PrazoGravado | None) -> int | None:
    item = limpeza(chave)
    if not item.editavel:
        return None
    return gravado.dias if gravado is not None and gravado.personalizado else item.padrao_dias


def _ator(ator: Any) -> tuple[str | None, str | None]:
    if ator is None:
        return None, None
    return str(getattr(ator, "id", "") or "") or None, getattr(ator, "email", None)


def _evento(ator: Any, acao: str, tipo: str, chave: str, depois: dict[str, Any]) -> AuditEvent:
    ator_id, _ = _ator(ator)
    return AuditEvent(id=f"aud_{uuid4().hex}", actor_type="user" if ator is not None else "system", actor_id=ator_id,
                      action=acao, resource_type=tipo, resource_id=chave, after=depois, occurred_at=datetime.now(UTC))


class ListarLimites:
    def __init__(self, repositorio: Any) -> None:
        self.repositorio = repositorio

    def execute(self, valores_de_arquivo: dict[str, int]) -> list[dict[str, Any]]:
        gravados = self.repositorio.limites()
        linhas = []
        for item in LIMITES:
            gravado = gravados.get(item.chave)
            if item.origem == "arquivo":
                valor, personalizado = valores_de_arquivo.get(item.chave, item.padrao), False
            elif gravado is None:
                valor, personalizado = item.padrao, False
            else:
                valor, personalizado = min(max(gravado[0], item.minimo), item.maximo), gravado[0] != item.padrao
            linhas.append({**asdict(item), "valor": valor, "personalizado": personalizado,
                           "atualizado_em": gravado[1] if gravado else None})
        return linhas


class DefinirLimite:
    def __init__(self, repositorio: Any, audit: Any, transaction: Any) -> None:
        self.repositorio = repositorio
        self.audit = audit
        self.transaction = transaction

    def execute(self, ator: Any, chave: str, valor: int) -> None:
        item = limite(chave)
        validar_limite(chave, valor)
        antes = self.repositorio.limites().get(chave)
        self.repositorio.gravar_limite(item, valor)
        self.audit.append(_evento(ator, "limite.definido", "system_limit", chave,
                                  {"valor": valor, "antes": antes[0] if antes else item.padrao}))
        self.transaction.commit()


class ListarLimpezas:
    def __init__(self, repositorio: Any) -> None:
        self.repositorio = repositorio

    def execute(self) -> list[dict[str, Any]]:
        gravados = self.repositorio.prazos()
        linhas = []
        for item in LIMPEZAS:
            gravado = gravados.get(item.chave)
            linhas.append({**asdict(item), "dias": dias_em_vigor(item.chave, gravado),
                           "personalizado": bool(gravado and gravado.personalizado),
                           "atualizado_por": gravado.atualizado_por if gravado else None,
                           "atualizado_em": gravado.atualizado_em if gravado else None,
                           "ultima_limpeza_em": gravado.ultima_limpeza_em if gravado else None,
                           "ultima_limpeza_apagados": gravado.ultima_limpeza_apagados if gravado else None,
                           "total_apagados": gravado.total_apagados if gravado else 0})
        return linhas


class DefinirPrazoDeLimpeza:
    """``dias`` nulo desliga a regra; ``voltar_ao_padrao`` apaga a personalização."""

    def __init__(self, repositorio: Any, audit: Any, transaction: Any) -> None:
        self.repositorio = repositorio
        self.audit = audit
        self.transaction = transaction

    def execute(self, ator: Any, chave: str, dias: int | None, voltar_ao_padrao: bool = False) -> None:
        item = limpeza(chave)
        if not voltar_ao_padrao:
            validar_prazo(chave, dias)
        elif not item.editavel:
            validar_prazo(chave, None)
        antes = dias_em_vigor(chave, self.repositorio.prazos().get(chave))
        _, email = _ator(ator)
        self.repositorio.gravar_prazo(chave, None if voltar_ao_padrao else dias, not voltar_ao_padrao, email,
                                      datetime.now(UTC))
        depois = item.padrao_dias if voltar_ao_padrao else dias
        self.audit.append(_evento(ator, "limpeza.prazo_definido", "limpeza", chave,
                                  {"dias": depois, "antes": antes, "padrao": voltar_ao_padrao}))
        self.transaction.commit()


class AplicarLimpezaDoSistema:
    """Uma passada: cada regra com prazo apaga um lote do que passou do prazo.

    Uma regra que falha não para as outras (o erro vai para o log). Cada regra é gravada à parte.
    """

    def __init__(self, repositorio: Any, limpadores: dict[str, Callable[[datetime, int], int]], audit: Any,
                 transaction: Any, agora: Callable[[], datetime] = lambda: datetime.now(UTC), lote: int = LOTE) -> None:
        self.repositorio = repositorio
        self.limpadores = limpadores
        self.audit = audit
        self.transaction = transaction
        self.agora = agora
        self.lote = lote

    def execute(self) -> dict[str, int]:
        agora = self.agora()
        gravados = self.repositorio.prazos()
        feito: dict[str, int] = {}
        for item in LIMPEZAS:
            if not item.editavel:
                continue
            ate = corte(agora, dias_em_vigor(item.chave, gravados.get(item.chave)))
            limpador = self.limpadores.get(item.chave)
            if ate is None or limpador is None:
                continue
            try:
                apagados = int(limpador(ate, self.lote))
                self.repositorio.registrar_passada(item.chave, apagados, agora)
                if apagados:
                    self.audit.append(_evento(None, "limpeza.aplicada", "limpeza", item.chave,
                                              {"apagados": apagados, "antes_de": ate.isoformat()}))
                self.transaction.commit()
                feito[item.chave] = apagados
            except Exception:  # uma regra com problema não segura as outras
                self.transaction.rollback()
                log.exception("Limpeza %s falhou", item.chave)
        return feito
