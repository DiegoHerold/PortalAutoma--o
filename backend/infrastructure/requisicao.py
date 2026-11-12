"""A requisição HTTP em andamento: um identificador que liga tudo o que ela gerou na auditoria,
mais o IP e o navegador de quem pediu. Preenchido pelo registro de requisições (middleware)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Requisicao:
    correlacao: str
    ip: str | None = None
    navegador: str | None = None


atual: ContextVar[Requisicao | None] = ContextVar("requisicao_atual", default=None)
