"""Regras da fila: ordem, previsão de início e término, escolha do próximo job e motivos.

Funções puras. A previsão e o despacho usam a MESMA ordem e a mesma escolha de máquina,
para o que a tela mostra não divergir do que acontece:

- Ordem: prioridade maior primeiro; depois a posição manual (quem tem vem antes); depois a
  ordem de chegada do lote; dentro do mesmo lote, a maior estimativa primeiro (os mais
  longos primeiro). Job sem estimativa vai depois dos que têm, dentro do lote.
- Cada job vai para a máquina compatível que fica livre antes. Job que precisa voltar para
  uma máquina (continuar de onde parou) só vai para ela.
- Tela: no máximo um job por máquina, somando agente e modo direto.
- Nada é inventado: sem estimativa, a previsão fica vazia e diz o motivo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

TELA = "interactive"

# Motivos de "sem previsão" e de espera (texto na tela fica no Portal, com nomes).
SEM_HISTORICO = "sem_historico_etapa"
AGUARDANDO_SEM_PREVISAO = "aguardando_job_sem_previsao"
ACIMA_DA_ESTIMATIVA = "acima_da_estimativa"
MAQUINA_SEM_SINAL = "maquina_sem_sinal"
SESSAO_BLOQUEADA = "sessao_bloqueada"
SEM_MAQUINA_COMPATIVEL = "sem_maquina_compativel"
JOB_PERDIDO_NA_MAQUINA = "job_perdido_na_maquina"
MAQUINA_OCUPADA = "maquina_ocupada"


@dataclass(frozen=True)
class JobNaFila:
    id: str
    pool: str
    prioridade: int
    lote: str
    enfileirado_em: datetime
    estimativa_s: float | None
    maquinas_compativeis: frozenset[str]
    posicao_manual: int | None = None
    maquina_obrigatoria: str | None = None
    motivos_estimativa: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmExecucao:
    """Job rodando numa máquina, com o que falta (None = desconhecido)."""

    job_id: str
    pool: str
    restante_s: float | None
    motivo: str | None = None   # por que o restante é desconhecido


@dataclass(frozen=True)
class Maquina:
    id: str
    online: bool
    capacidade: dict[str, int]
    rodando: tuple[EmExecucao, ...] = ()
    sessao_bloqueada: bool = False
    job_perdido: bool = False


@dataclass(frozen=True)
class Previsao:
    job_id: str
    posicao: int
    maquina_id: str | None
    inicio: datetime | None
    fim: datetime | None
    motivos: tuple[str, ...] = ()
    aguardando: str | None = None   # job (rodando ou na fila) sem previsão que segura este início


@dataclass
class _Vaga:
    maquina: str
    livre_em: datetime | None
    motivos: tuple[str, ...] = field(default_factory=tuple)
    aguardando: str | None = None


def ordenar(jobs: Iterable[JobNaFila]) -> list[JobNaFila]:
    def chave(job: JobNaFila) -> tuple:
        return (
            -job.prioridade,
            job.posicao_manual is None,
            job.posicao_manual if job.posicao_manual is not None else 0,
            job.enfileirado_em,
            job.lote,
            job.estimativa_s is None,
            -(job.estimativa_s or 0.0),
            job.id,
        )

    return sorted(jobs, key=chave)


def disponivel(maquina: Maquina) -> bool:
    return maquina.online and not maquina.sessao_bloqueada and not maquina.job_perdido


def motivos_da_maquina(maquina: Maquina) -> tuple[str, ...]:
    motivos = []
    if not maquina.online:
        motivos.append(MAQUINA_SEM_SINAL)
    if maquina.sessao_bloqueada:
        motivos.append(SESSAO_BLOQUEADA)
    if maquina.job_perdido:
        motivos.append(JOB_PERDIDO_NA_MAQUINA)
    return tuple(motivos)


def _vagas(maquinas: Sequence[Maquina], agora: datetime) -> dict[str, list[_Vaga]]:
    """Vagas por pool em cada máquina disponível, com a hora em que cada uma fica livre."""
    vagas: dict[str, list[_Vaga]] = {}
    for maquina in maquinas:
        if not disponivel(maquina):
            continue
        for pool, capacidade in maquina.capacidade.items():
            if pool == TELA:
                capacidade = min(capacidade, 1)  # tela: uma por máquina, nos dois modos
            ocupadas = [r for r in maquina.rodando if r.pool == pool]
            for indice in range(max(capacidade, 0)):
                if indice < len(ocupadas):
                    r = ocupadas[indice]
                    if r.restante_s is None:
                        vaga = _Vaga(maquina.id, None, (r.motivo or AGUARDANDO_SEM_PREVISAO,), r.job_id)
                    else:
                        vaga = _Vaga(maquina.id, agora + timedelta(seconds=max(r.restante_s, 0.0)))
                else:
                    vaga = _Vaga(maquina.id, agora)
                vagas.setdefault(f"{maquina.id}|{pool}", []).append(vaga)
    return vagas


def prever(jobs: Iterable[JobNaFila], maquinas: Sequence[Maquina], agora: datetime) -> list[Previsao]:
    """Início e término previstos de cada job, na ordem da fila."""
    por_id = {m.id: m for m in maquinas}
    vagas = _vagas(maquinas, agora)
    previsoes: list[Previsao] = []
    for posicao, job in enumerate(ordenar(jobs), 1):
        alvos = {job.maquina_obrigatoria} if job.maquina_obrigatoria else set(job.maquinas_compativeis)
        candidatas = [v for m in sorted(alvos) for v in vagas.get(f"{m}|{job.pool}", [])]
        if not candidatas:
            existentes = [por_id[m] for m in sorted(alvos) if m in por_id]
            motivos = tuple(dict.fromkeys(x for m in existentes for x in motivos_da_maquina(m))) or (SEM_MAQUINA_COMPATIVEL,)
            previsoes.append(Previsao(job.id, posicao, None, None, None, motivos))
            continue
        conhecidas = [v for v in candidatas if v.livre_em is not None]
        if conhecidas:
            vaga = min(conhecidas, key=lambda v: (v.livre_em, v.maquina))
        else:
            vaga = min(candidatas, key=lambda v: v.maquina)
        inicio = vaga.livre_em
        motivos = tuple(dict.fromkeys((*vaga.motivos, *job.motivos_estimativa)))
        fim = inicio + timedelta(seconds=job.estimativa_s) if inicio is not None and job.estimativa_s is not None else None
        previsoes.append(Previsao(job.id, posicao, vaga.maquina, inicio, fim, motivos,
                                  vaga.aguardando if inicio is None else None))
        # A vaga passa a ficar livre quando este job terminar (ou em hora desconhecida).
        vaga.livre_em = fim
        vaga.motivos = () if fim is not None else ((AGUARDANDO_SEM_PREVISAO,) if job.estimativa_s is None else vaga.motivos)
        vaga.aguardando = None if fim is not None else (job.id if job.estimativa_s is None else vaga.aguardando)
    return previsoes


def proximo_job(maquina: Maquina, pool: str, jobs: Iterable[JobNaFila]) -> JobNaFila | None:
    """O despacho: a máquina com vaga livre pega o primeiro job compatível na ordem da fila."""
    if not disponivel(maquina) or vagas_livres(maquina, pool) <= 0:
        return None
    for job in ordenar(jobs):
        if job.pool != pool:
            continue
        if job.maquina_obrigatoria is not None and job.maquina_obrigatoria != maquina.id:
            continue
        if job.maquina_obrigatoria is None and maquina.id not in job.maquinas_compativeis:
            continue
        return job
    return None


def vagas_livres(maquina: Maquina, pool: str) -> int:
    capacidade = maquina.capacidade.get(pool, 0)
    if pool == TELA:
        capacidade = min(capacidade, 1)  # tela: uma por máquina, nos dois modos
    return capacidade - sum(1 for r in maquina.rodando if r.pool == pool)


def chave_de_duplicata(automation_id: int, itens: Iterable[str], parametros: dict[str, Any]) -> str:
    """Mesma automação, mesmos itens e mesmos parâmetros = mesmo pedido."""
    texto = json.dumps({"a": automation_id, "i": sorted(set(itens)), "p": parametros},
                       sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def agrupar(itens: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Um job por grupo, na ordem em que o primeiro item de cada grupo apareceu. Item sem
    grupo é um grupo dele mesmo. O líder (item cuja chave é o grupo) vai primeiro."""
    grupos: dict[str, list[dict[str, Any]]] = {}
    for item in itens:
        grupo = str(item.get("grupo") or item["chave"])
        grupos.setdefault(grupo, []).append(item)
    saida = []
    for grupo, membros in grupos.items():
        lider = [m for m in membros if str(m["chave"]) == grupo]
        saida.append(lider + [m for m in membros if str(m["chave"]) != grupo])
    return saida


def pode_repetir_sozinho(pool: str, seguro_repetir: bool) -> bool:
    """Tela nunca repete sozinha, a menos que o manifesto declare que é seguro."""
    return pool != TELA or seguro_repetir


def maquina_da_retomada(maquina_anterior: str | None, estado_central: bool) -> str | None:
    """Continuar de onde parou volta para a mesma máquina, salvo estado central."""
    return None if estado_central else maquina_anterior
