"""Retenção por automação (Fase 6): por quantos dias guardar as imagens e os logs.

Fase 8: também os arquivos que a automação entregou (planilhas, TXT).

Sem prazo definido, nada é apagado (decisão de 10/11/2026: sem padrão). O histórico de
tempos (``step_runs``) não entra aqui: a estimativa nunca muda por causa da limpeza.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DIAS_MINIMO, DIAS_MAXIMO = 1, 3650


class PrazoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class RetencaoDaAutomacao:
    automation_id: int
    imagens_dias: int | None = None
    logs_dias: int | None = None
    arquivos_dias: int | None = None


def validar(automation_id: int, imagens_dias: int | None, logs_dias: int | None,
            arquivos_dias: int | None = None) -> RetencaoDaAutomacao:
    for nome, dias in (("imagens", imagens_dias), ("logs", logs_dias), ("arquivos", arquivos_dias)):
        if dias is not None and not DIAS_MINIMO <= dias <= DIAS_MAXIMO:
            raise PrazoInvalido(f"o prazo de {nome} vai de {DIAS_MINIMO} a {DIAS_MAXIMO} dias")
    return RetencaoDaAutomacao(automation_id, imagens_dias, logs_dias, arquivos_dias)


def corte(agora: datetime, dias: int | None) -> datetime | None:
    """Tudo criado antes deste momento sai. ``None``: sem prazo, nada sai."""
    if dias is None:
        return None
    return agora - timedelta(days=dias)
