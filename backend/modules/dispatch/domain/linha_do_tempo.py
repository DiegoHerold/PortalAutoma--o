"""Linha do tempo por máquina (Gantt da Fase 5): o que rodou, o que roda e o que a fila prevê.

Regras puras: recorta cada bloco na janela, calcula a posição em porcentagem e nunca
inventa fim. Bloco rodando vai até a previsão de término (ou até agora, se não há
previsão); bloco previsto sem término fica marcado "sem previsão" e vai até o fim da janela.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

FEITO, RODANDO, PREVISTO = "feito", "rodando", "previsto"
LARGURA_MINIMA = 0.6  # % da janela: bloco curtíssimo continua clicável


@dataclass(frozen=True)
class Bloco:
    maquina_id: str
    tipo: str
    inicio: datetime
    fim: datetime | None
    execucao_id: str | None = None
    job_id: str | None = None
    automacao: str | None = None
    itens: tuple[str, ...] = ()
    situacao: str | None = None


def _fim_desenhado(bloco: Bloco, agora: datetime, fim_janela: datetime) -> tuple[datetime, bool]:
    """Fim usado no desenho e se ele é conhecido."""
    if bloco.fim is not None:
        return bloco.fim, True
    if bloco.tipo == RODANDO:
        return max(agora, bloco.inicio), False
    return fim_janela, False


def montar(maquinas: list[tuple[str, str]], blocos: list[Bloco], inicio_janela: datetime, fim_janela: datetime,
           agora: datetime) -> list[dict[str, Any]]:
    if fim_janela <= inicio_janela:
        raise ValueError("a janela precisa terminar depois de começar")
    total = (fim_janela - inicio_janela).total_seconds()
    por_maquina: dict[str, list[dict[str, Any]]] = {m: [] for m, _ in maquinas}
    for bloco in sorted(blocos, key=lambda b: (b.inicio, b.tipo)):
        if bloco.maquina_id not in por_maquina:
            continue
        fim, conhecido = _fim_desenhado(bloco, agora, fim_janela)
        if fim <= inicio_janela or bloco.inicio >= fim_janela:
            continue
        de, ate = max(bloco.inicio, inicio_janela), min(fim, fim_janela)
        esquerda = (de - inicio_janela).total_seconds() / total * 100
        largura = max((ate - de).total_seconds() / total * 100, LARGURA_MINIMA)
        por_maquina[bloco.maquina_id].append({
            "tipo": bloco.tipo, "inicio": bloco.inicio.isoformat(), "fim": bloco.fim.isoformat() if bloco.fim else None,
            "fim_conhecido": conhecido, "esquerda": round(esquerda, 3), "largura": round(min(largura, 100 - esquerda), 3),
            "cortado_no_inicio": bloco.inicio < inicio_janela, "cortado_no_fim": fim > fim_janela,
            "execucao_id": bloco.execucao_id, "job_id": bloco.job_id, "automacao": bloco.automacao,
            "itens": list(bloco.itens), "situacao": bloco.situacao,
        })
    return [{"maquina_id": m, "nome": nome, "blocos": por_maquina[m]} for m, nome in maquinas]


def marcas(inicio_janela: datetime, fim_janela: datetime, passo: timedelta = timedelta(hours=1)) -> list[dict[str, Any]]:
    """Horas cheias dentro da janela, com a posição em porcentagem (régua do Gantt)."""
    total = (fim_janela - inicio_janela).total_seconds()
    atual = inicio_janela.replace(minute=0, second=0, microsecond=0)
    if atual < inicio_janela:
        atual += passo
    saida = []
    while atual <= fim_janela:
        saida.append({"quando": atual.isoformat(), "posicao": round((atual - inicio_janela).total_seconds() / total * 100, 3)})
        atual += passo
    return saida
