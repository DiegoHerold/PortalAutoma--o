"""Fila: o que está esperando, por quê, onde e quando deve começar; e o despacho.

Previsão e despacho usam as mesmas regras (``modules.dispatch.domain.fila``). A
estimativa de cada job vem do histórico do Telemetry (regras das estimativas), sem
inventar número.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from modules.dispatch.domain.fila import (
    ACIMA_DA_ESTIMATIVA,
    AGUARDANDO_SEM_PREVISAO,
    TELA,
    EmExecucao,
    JobNaFila,
    Maquina,
    prever,
    proximo_job,
    vagas_livres,
)

TEXTOS = {
    "sem_historico_etapa": "rodando pela primeira vez, sem histórico de estimativas",
    "configuracao_mudou": "a configuração que muda o trabalho do item mudou",
    AGUARDANDO_SEM_PREVISAO: "aguardando o término de um job que não tem previsão",
    ACIMA_DA_ESTIMATIVA: "o job atual da máquina já passou da estimativa",
    "maquina_sem_sinal": "máquina sem sinal",
    "sessao_bloqueada": "sessão do Windows bloqueada",
    "sem_maquina_compativel": "nenhuma máquina tem esta automação",
    "job_perdido_na_maquina": "a máquina tem um job perdido aguardando decisão",
}
VALIDADE_TRAVA = timedelta(hours=24)


def _maquina_do_dominio(m: Any, restantes: dict[str, tuple[float | None, str | None]]) -> Maquina:
    online = any(a["online"] and a["habilitado"] for a in m.agentes) or any(d["com_sinal"] for d in m.diretas)
    bloqueada = any(a["bloqueada"] for a in m.agentes if a["online"])
    rodando = tuple(EmExecucao(r["job_id"], r["pool"], *restantes.get(r["job_id"], (None, AGUARDANDO_SEM_PREVISAO)))
                    for r in m.rodando)
    return Maquina(m.id, online, {k: int(v) for k, v in m.capacidade.items()}, rodando, bloqueada, m.perdido)


def _compativeis(maquinas: list[Any], automation_id: int | None) -> frozenset[str]:
    """Máquinas com Agent habilitado, ou com instância direta aprovada desta automação.
    (Quarentena e revogada não recebem jobs.)"""
    return frozenset(
        m.id for m in maquinas
        if any(a["habilitado"] for a in m.agentes)
        or any(d["automation_id"] == automation_id and d["status"] == "aprovada" for d in m.diretas)
    )


class MontarFila:
    """Estado da fila e das máquinas no formato das regras."""

    def __init__(self, reader: Any, estimar_job: Callable[..., Any], restante_rodando: Callable[..., Any],
                 nomes_etapas: Callable[[int], dict[str, str]] = lambda _versao: {}) -> None:
        self.reader = reader
        self.estimar_job = estimar_job            # (automation_version_id, itens, corte, job_id) -> EstimativaSoma
        self.restante_rodando = restante_rodando  # (execution_id, job_id, desde, agora) -> (segundos|None, motivo|None)
        self.nomes_etapas = nomes_etapas          # automation_version_id -> {chave da etapa: nome}

    def execute(self, agora: datetime) -> tuple[list[JobNaFila], list[Maquina], dict[str, Any], list[Any]]:
        lidas = self.reader.maquinas(agora)
        restantes = {r["job_id"]: self.restante_rodando(r["execution_id"], r["job_id"], r["desde"], agora)
                     for m in lidas for r in m.rodando}
        maquinas = [_maquina_do_dominio(m, restantes) for m in lidas]
        jobs: list[JobNaFila] = []
        detalhes: dict[str, Any] = {}
        for linha in self.reader.jobs_na_fila():
            tarefa = linha["tarefa"]
            automation_id = self.reader.automation_id(tarefa.automation_version_id)
            soma = self.estimar_job(tarefa.automation_version_id, linha["itens"], agora, tarefa.id)
            motivos = tuple(dict.fromkeys(
                p.motivo for p in getattr(soma, "partes", ()) if getattr(p, "motivo", None))) if not soma.completa else ()
            jobs.append(JobNaFila(
                id=tarefa.id, pool=tarefa.pool or "background", prioridade=int(tarefa.priority or 0),
                lote=tarefa.enqueue_batch_id or tarefa.execution_id, enfileirado_em=tarefa.enqueued_at or tarefa.created_at,
                estimativa_s=soma.segundos if soma.completa else None,
                maquinas_compativeis=_compativeis(lidas, automation_id), posicao_manual=tarefa.manual_position,
                maquina_obrigatoria=tarefa.required_machine_id, motivos_estimativa=motivos))
            detalhes[tarefa.id] = {"tarefa": tarefa, "itens": linha["itens"], "automation_id": automation_id,
                                   "estimativa": soma}
        return jobs, maquinas, detalhes, lidas


def _lista(valores: list[str], limite: int = 3) -> str:
    return ", ".join(valores[:limite]) + (f" e mais {len(valores) - limite}" if len(valores) > limite else "")


def _partes_sem_base(soma: Any, codigo: str) -> list[Any]:
    return [p for p in getattr(soma, "partes", ()) if getattr(p, "motivo", None) == codigo]


class VerFila:
    """A fila como o operador lê: cada motivo diz de quem é (etapa, item ou o job que segura a vaga).

    Motivo que cita outro job leva ``automation_id`` para a API trocar o texto por um genérico
    quando o usuário não pode ver aquela automação.
    """

    def __init__(self, montar: MontarFila) -> None:
        self.montar = montar

    def _etapas_sem_base(self, d: dict[str, Any]) -> list[str]:
        nomes = self.montar.nomes_etapas(d["tarefa"].automation_version_id)
        partes = [p for p in getattr(d["estimativa"], "partes", ()) if getattr(p, "segundos", 0) is None]
        return list(dict.fromkeys(nomes.get(p.etapa, p.etapa) for p in partes))

    def _motivo(self, codigo: str, d: dict[str, Any], aguardando: str | None,
                detalhes: dict[str, Any]) -> dict[str, Any]:
        motivo: dict[str, Any] = {"codigo": codigo, "texto": TEXTOS.get(codigo, codigo)}
        if codigo in ("sem_historico_etapa", "configuracao_mudou"):
            partes = _partes_sem_base(d["estimativa"], codigo)
            nomes = self.montar.nomes_etapas(d["tarefa"].automation_version_id)
            etapas = list(dict.fromkeys(nomes.get(p.etapa, p.etapa) for p in partes if p.etapa in nomes))
            itens = sorted({p.item for p in partes if p.item})
            if codigo == "sem_historico_etapa" and not nomes:
                motivo["texto"] = "a automação não declara etapas no manifesto, então não há base para estimar"
            elif codigo == "sem_historico_etapa" and etapas:
                sujeito = f"etapa {etapas[0]}" if len(etapas) == 1 else f"etapas {_lista(etapas)}"
                alvo = f" (item {itens[0]})" if len(itens) == 1 else (f" (itens {_lista(itens)})" if itens else "")
                motivo["texto"] = f"{sujeito}{alvo} rodando pela primeira vez, sem histórico de estimativas"
            elif codigo == "configuracao_mudou" and itens:
                motivo["texto"] = (f"a configuração que muda o trabalho mudou para {'o item' if len(itens) == 1 else 'os itens'} "
                                   f"{_lista(itens)}: o histórico anterior não serve de base")
        elif codigo in (AGUARDANDO_SEM_PREVISAO, ACIMA_DA_ESTIMATIVA) and aguardando:
            if aguardando in detalhes:
                outro = detalhes[aguardando]
                automation_id, itens = outro["automation_id"], [i["chave"] for i in outro["itens"]]
            else:
                automation_id, itens = self.montar.reader.descrever_job(aguardando)
            nome = self.montar.reader.automation_name(automation_id) or "outro job"
            quem = f"{nome} ({_lista(itens)})" if itens else nome
            motivo["texto"] = (f"aguardando o término de {quem}, que está sem previsão" if codigo == AGUARDANDO_SEM_PREVISAO
                               else f"aguardando {quem}, que já passou da estimativa")
            motivo["automation_id"] = automation_id
        return motivo

    def execute(self, agora: datetime) -> dict[str, Any]:
        jobs, maquinas, detalhes, lidas = self.montar.execute(agora)
        nomes = {m.id: m.nome for m in lidas}
        previsoes = prever(jobs, maquinas, agora)
        linhas = []
        for previsao in previsoes:
            d = detalhes[previsao.job_id]
            tarefa, soma = d["tarefa"], d["estimativa"]
            linhas.append({
                "posicao": previsao.posicao,
                "job_id": tarefa.id,
                "execution_id": tarefa.execution_id,
                "automation_id": d["automation_id"],
                "automacao": self.montar.reader.automation_name(d["automation_id"]),
                "pool": tarefa.pool,
                "itens": [i["chave"] for i in d["itens"]],
                "prioridade": tarefa.priority,
                "posicao_manual": tarefa.manual_position,
                "maquina_prevista": previsao.maquina_id,
                "maquina_prevista_nome": nomes.get(previsao.maquina_id),
                "maquina_obrigatoria": tarefa.required_machine_id,
                "inicio_previsto": previsao.inicio.isoformat() if previsao.inicio else None,
                "termino_previsto": previsao.fim.isoformat() if previsao.fim else None,
                "estimativa_s": soma.segundos if soma.completa else None,
                "estimativa_minima_s": soma.segundos if not soma.completa else None,
                "etapas_sem_base": self._etapas_sem_base(d),
                "motivos": [self._motivo(c, d, previsao.aguardando, detalhes) for c in previsao.motivos],
                "enfileirado_em": (tarefa.enqueued_at or tarefa.created_at).isoformat(),
            })
        perdidos = []
        for p in self.montar.reader.jobs_perdidos():
            tarefa = p["tarefa"]
            automation_id = self.montar.reader.automation_id(tarefa.automation_version_id)
            perdidos.append({
                "job_id": tarefa.id, "execution_id": tarefa.execution_id, "automation_id": automation_id,
                "automacao": self.montar.reader.automation_name(automation_id),
                "itens": list((tarefa.input or {}).get("itens") or []), "maquina_id": p["maquina_id"],
                "maquina_nome": p["maquina_nome"], "perdido_em": tarefa.lost_at.isoformat() if tarefa.lost_at else None,
                "motivo": tarefa.failure_summary,
                "estado_central": bool((tarefa.retry_policy or {}).get("central_state", False)),
            })
        return {
            "gerado_em": agora.isoformat(),
            "jobs": linhas,
            "perdidos": perdidos,
            "maquinas": [{
                "id": m.id, "nome": nomes.get(m.id), "online": m.online, "sessao_bloqueada": m.sessao_bloqueada,
                "job_perdido": m.job_perdido, "capacidade": m.capacidade,
                "rodando": [{"job_id": r.job_id, "pool": r.pool, "restante_s": r.restante_s,
                             "motivo": TEXTOS.get(r.motivo or "", r.motivo)} for r in m.rodando],
                "vagas_tela": vagas_livres(m, TELA),
            } for m in maquinas],
        }


class DespacharFila:
    """Cada máquina com vaga pega o primeiro job compatível, na mesma ordem da previsão.

    Agent: o job fica ``ready`` só para aquele Agent (oferta e commit continuam no fluxo
    existente) e leva a trava de tela da máquina. Modo direto: a trava de tela é tomada
    aqui (o índice único garante uma por máquina) e a tentativa direta é criada.
    """

    def __init__(self, montar: MontarFila, reader: Any, tasks: Any, iniciar_direta: Callable[..., Any],
                 transaction: Any) -> None:
        self.montar = montar
        self.reader = reader
        self.tasks = tasks
        self.iniciar_direta = iniciar_direta
        self.transaction = transaction

    def execute(self, agora: datetime) -> list[dict[str, Any]]:
        # Oferta recusada não é falha: o job volta para a fila e é planejado de novo.
        for parado in self.reader.ready_sem_tentativa():
            tarefa = self.tasks.get(parado.id)
            requisitos = dict(tarefa.requirements_snapshot or {})
            requisitos.pop("dispatch", None)
            requisitos["exclusive_resources"] = [r for r in requisitos.get("exclusive_resources") or []
                                                 if not (isinstance(r, dict) and r.get("scope") == "maquina_tela")]
            self.tasks.save(replace(tarefa, status="queued", requirements_snapshot=requisitos, last_scheduling_failure=None))
        jobs, maquinas, detalhes, lidas = self.montar.execute(agora)
        lidas_por_id = {m.id: m for m in lidas}
        restantes = list(jobs)
        entregues: list[dict[str, Any]] = []
        for maquina in sorted(maquinas, key=lambda m: m.id):
            for pool in sorted(maquina.capacidade):
                while restantes:
                    job = proximo_job(maquina, pool, restantes)
                    if job is None:
                        break
                    restantes.remove(job)
                    destino = self._entregar(job, maquina, lidas_por_id[maquina.id], detalhes[job.id], agora)
                    if destino is None:
                        continue
                    entregues.append(destino)
                    maquina = replace(maquina, rodando=(*maquina.rodando, EmExecucao(job.id, job.pool, None)))
        self.transaction.commit()
        return entregues

    def _entregar(self, job: JobNaFila, maquina: Maquina, lida: Any, detalhe: dict[str, Any], agora: datetime):
        tarefa = self.tasks.get(job.id)
        agente = next((a for a in lida.agentes if a["online"] and a["habilitado"] and not a["bloqueada"]), None)
        if agente is not None:
            requisitos = dict(tarefa.requirements_snapshot or {})
            requisitos["dispatch"] = {**(requisitos.get("dispatch") or {}), "required_agent_id": agente["id"],
                                      "machine_id": maquina.id}
            if job.pool == TELA:
                travas = [r for r in requisitos.get("exclusive_resources") or []
                          if not (isinstance(r, dict) and r.get("scope") == "maquina_tela")]
                requisitos["exclusive_resources"] = [*travas, {"key": f"machine:{maquina.id}:screen", "scope": "maquina_tela"}]
            self.tasks.save(replace(tarefa, status="ready", ready_at=agora, requirements_snapshot=requisitos))
            return {"job_id": job.id, "maquina_id": maquina.id, "modo": "agente", "executor": agente["id"]}
        direta = next((d for d in lida.diretas if d["automation_id"] == detalhe["automation_id"]
                       and d["status"] == "aprovada" and d["com_sinal"]), None)
        if direta is None:
            return None
        tentativa_id = f"att_{uuid4().hex}"
        ponto = self.reader.savepoint()  # tentativa e trava juntas: sem trava, nada fica gravado
        self.iniciar_direta(task_execution_id=job.id, attempt_id=tentativa_id, direct_instance_id=direta["id"],
                            machine_id=maquina.id, now=agora)
        if job.pool == TELA and not self.reader.tentar_trava_de_tela(
                lock_id=f"lock_{uuid4().hex}", machine_id=maquina.id, attempt_id=tentativa_id, agora=agora,
                validade=VALIDADE_TRAVA):
            ponto.rollback()
            return None
        ponto.commit()
        return {"job_id": job.id, "maquina_id": maquina.id, "modo": "direto", "executor": direta["id"]}
