"""Regras de estimativa de tempo (validadas na Integração Contábil).

Funções puras: recebem o histórico já lido e devolvem a estimativa com a base de onde
ela veio. Nenhuma regra inventa número.

1. Cada item tem o seu histórico; um item nunca serve de base para outro.
2. Etapa = mediana das 5 últimas execuções concluídas daquela etapa, naquele item,
   naquela automação.
3. Etapa por tarefa = segundos por tarefa x tarefas restantes (na retomada, só o que falta).
4. Etapa com erro ou interrompida fica no histórico, mas não é base.
5. Etapa sem item usa todas as execuções da automação.
6. Mudou a configuração que altera o trabalho do item: a base zera.
7. Pausas (reinício, espera externa) ficam fora da duração.
8. A base de uma execução é só o que terminou antes dela.
9. Sem base: sem número, com o motivo, e fora da soma.
10. Job = soma das etapas; execução = soma dos jobs.
11. Toda estimativa diz de onde veio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Iterable, Sequence

AMOSTRAS = 5

SEM_HISTORICO = "sem_historico_etapa"
CONFIGURACAO_MUDOU = "configuracao_mudou"


@dataclass(frozen=True)
class EtapaDeclarada:
    """Etapa do manifesto, na ordem em que roda."""

    chave: str
    nome: str
    por_item: bool = True
    por_tarefa: bool = False


@dataclass(frozen=True)
class Medicao:
    """Uma parte de uma etapa medida numa tentativa (step_runs)."""

    execution_id: str
    automation_id: int
    etapa: str
    item: str | None
    assinatura: str
    situacao: str            # ok | erro | interrompida | executando
    tarefas: int
    duracao_s: float          # já sem as pausas (regra 7)
    fim: datetime | None


@dataclass(frozen=True)
class Base:
    tipo: str                 # "item" | "automacao"
    amostras: int

    def texto(self) -> str:
        alvo = {"item": "do item", "automacao": "da automação"}[self.tipo]
        return f"últimas {self.amostras} execuções {alvo}" if self.amostras != 1 else f"última execução {alvo}"


@dataclass(frozen=True)
class EstimativaEtapa:
    etapa: str
    item: str | None
    segundos: float | None
    base: Base | None
    motivo: str | None = None
    segundos_por_tarefa: float | None = None
    tarefas_restantes: int | None = None
    tarefas_origem: str | None = None  # declaradas | ultima_execucao


@dataclass(frozen=True)
class EstimativaSoma:
    """Soma de etapas (job) ou de jobs (execução). ``segundos`` é o mínimo conhecido
    quando ``sem_base`` > 0: as partes sem base ficam fora da soma, nunca viram zero."""

    segundos: float | None
    sem_base: int
    total: int
    partes: tuple = field(default_factory=tuple)

    @property
    def completa(self) -> bool:
        return self.sem_base == 0 and self.segundos is not None


def duracao_liquida(inicio: datetime, fim: datetime,
                    pausas: Iterable[tuple[datetime, datetime | None]]) -> tuple[float, float]:
    """Regra 7: (duração sem as pausas, segundos de pausa) da etapa entre ``inicio`` e ``fim``.

    Só conta a parte de cada pausa que cai dentro da etapa; pausas sobrepostas não são
    descontadas duas vezes; pausa ainda aberta vai até o ``fim``."""
    trechos = sorted((max(a, inicio), min(b or fim, fim)) for a, b in pausas)
    pausado = 0.0
    atual_ini: datetime | None = None
    atual_fim: datetime | None = None
    for a, b in trechos:
        if b <= a:
            continue
        if atual_fim is None or a > atual_fim:
            if atual_fim is not None:
                pausado += (atual_fim - atual_ini).total_seconds()
            atual_ini, atual_fim = a, b
        elif b > atual_fim:
            atual_fim = b
    if atual_fim is not None:
        pausado += (atual_fim - atual_ini).total_seconds()
    bruta = max((fim - inicio).total_seconds(), 0.0)
    return max(bruta - pausado, 0.0), pausado


def execucoes_concluidas(medicoes: Iterable[Medicao]) -> list[tuple[datetime, float, int]]:
    """Junta as partes de cada execução (retomada) numa execução só (decisão 7).

    A execução conta se a etapa foi concluída: a última parte terminou ``ok``. As partes
    anteriores, mesmo com erro ou interrompidas, entram na soma, porque foram trabalho
    daquela execução. Se a última parte não terminou ``ok``, ou alguma parte ainda está
    aberta, a execução fica fora da base (regra 4).
    Devolve (fim, segundos, tarefas) da mais recente para a mais antiga."""
    por_execucao: dict[str, list[Medicao]] = {}
    for medicao in medicoes:
        por_execucao.setdefault(medicao.execution_id, []).append(medicao)
    concluidas = []
    for partes in por_execucao.values():
        if any(p.fim is None for p in partes):
            continue
        ultima = max(partes, key=lambda p: p.fim)
        if ultima.situacao != "ok":
            continue
        concluidas.append((ultima.fim, sum(p.duracao_s for p in partes), sum(p.tarefas for p in partes)))
    concluidas.sort(key=lambda c: c[0], reverse=True)
    return concluidas


def estimar_etapa(etapa: EtapaDeclarada, automation_id: int, item: str | None, assinatura: str,
                  historico: Sequence[Medicao], corte: datetime, tarefas_restantes: int | None = None,
                  execucao_atual: str | None = None) -> EstimativaEtapa:
    """Estimativa de uma etapa para um item, com base só no que terminou antes de ``corte``."""
    alvo = item if etapa.por_item else None
    validas = [
        m for m in historico
        if m.automation_id == automation_id and m.etapa == etapa.chave
        and m.execution_id != execucao_atual
        and (not etapa.por_item or m.item == item)
        and m.fim is not None and m.fim < corte
    ]
    if etapa.por_item:
        mesma_configuracao = [m for m in validas if m.assinatura == assinatura]
        if not mesma_configuracao:
            motivo = CONFIGURACAO_MUDOU if execucoes_concluidas(validas) else SEM_HISTORICO
            return EstimativaEtapa(etapa.chave, alvo, None, None, motivo)
        validas = mesma_configuracao

    ultimas = execucoes_concluidas(validas)[:AMOSTRAS]
    if not ultimas:
        return EstimativaEtapa(etapa.chave, alvo, None, None, SEM_HISTORICO)
    base = Base("item" if etapa.por_item else "automacao", len(ultimas))

    if not etapa.por_tarefa:
        return EstimativaEtapa(etapa.chave, alvo, median(s for _, s, _ in ultimas), base)

    com_tarefas = [(s, t) for _, s, t in ultimas if t > 0]
    if not com_tarefas:
        return EstimativaEtapa(etapa.chave, alvo, None, None, SEM_HISTORICO)
    por_tarefa = median(s / t for s, t in com_tarefas)
    base = Base(base.tipo, len(com_tarefas))
    origem = "declaradas"
    if tarefas_restantes is None:
        # Antes de a automação declarar, vale a quantidade da última execução deste mesmo item.
        tarefas_restantes, origem = com_tarefas[0][1], "ultima_execucao"
    restantes = max(tarefas_restantes, 0)
    return EstimativaEtapa(etapa.chave, alvo, por_tarefa * restantes, base, None, por_tarefa, restantes, origem)


def somar(partes: Sequence[EstimativaEtapa | EstimativaSoma]) -> EstimativaSoma:
    """Regra 10: soma o que tem base; o que não tem fica fora e é contado (em etapas)."""
    conhecidas = [p.segundos for p in partes if p.segundos is not None]
    sem_base = total = 0
    for parte in partes:
        if isinstance(parte, EstimativaSoma):
            sem_base += parte.sem_base
            total += parte.total
        else:
            total += 1
            sem_base += parte.segundos is None
    return EstimativaSoma(sum(conhecidas) if conhecidas else None, sem_base, total, tuple(partes))
