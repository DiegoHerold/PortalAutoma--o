"""Como a Auditoria agrupa os eventos (12/11/2026).

Quatro tipos, para filtrar a linha do tempo:
- ``acesso``: entrar e sair, telas abertas, sessões das máquinas;
- ``execucao``: pedir, acompanhar, ver telas, parar execuções;
- ``sistema``: o que as máquinas e o próprio Portal fizeram sozinhos;
- ``alteracao``: o resto do que uma pessoa fez (criar, editar, apagar...).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TIPOS = ("alteracao", "acesso", "execucao", "sistema")

ACESSO_EXATO = ("login_succeeded", "login_failed", "logout")
ACESSO_PREFIXOS = ("tela.", "direto.sessao", "direto.desafio")
EXECUCAO_PREFIXOS = ("execucao.", "execution", "fila.", "job.", "schedule.trigger", "automacao.arquivo.baixado")
AGRUPAMENTOS = ("dia", "usuario", "acao")
FUSO = "America/Sao_Paulo"  # os dias da tela são os de São Paulo


def tipo_do_evento(acao: str, tipo_de_ator: str) -> str:
    if acao in ACESSO_EXATO or acao.startswith(ACESSO_PREFIXOS):
        return "acesso"
    if acao.startswith(EXECUCAO_PREFIXOS):
        return "execucao"
    if tipo_de_ator != "user":
        return "sistema"
    return "alteracao"


class FiltroInvalido(ValueError):
    pass


def validar_tipo(valor: str | None) -> str | None:
    if valor in (None, ""):
        return None
    if valor not in TIPOS:
        raise FiltroInvalido(f"tipo: use {', '.join(TIPOS)}")
    return valor


def validar_agrupamento(valor: str) -> str:
    if valor not in AGRUPAMENTOS:
        raise FiltroInvalido(f"por: use {', '.join(AGRUPAMENTOS)}")
    return valor


def intervalo(de: date | None, ate: date | None) -> tuple[datetime | None, datetime | None]:
    """Datas inclusivas da tela viram [início do primeiro dia, início do dia seguinte ao último)."""
    if de and ate and de > ate:
        raise FiltroInvalido("de: a data inicial é depois da final")
    fuso = ZoneInfo(FUSO)
    inicio = datetime(de.year, de.month, de.day, tzinfo=fuso) if de else None
    fim = datetime(ate.year, ate.month, ate.day, tzinfo=fuso) + timedelta(days=1) if ate else None
    return inicio, fim
