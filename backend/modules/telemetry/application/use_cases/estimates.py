"""Estimativas por etapa, item, job e execução, e o histórico de tempos por item.

As regras ficam em ``modules.telemetry.domain.estimativas``. Aqui só se lê o histórico,
se congela a estimativa no início (regra 8) e se monta a resposta para a tela.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable

from modules.telemetry.application.dto import AttemptTelemetryContextDTO
from modules.telemetry.domain.estimativas import (
    AMOSTRAS,
    Base,
    EstimativaEtapa,
    EtapaDeclarada,
    estimar_etapa,
    execucoes_concluidas,
    somar,
)

TEXTOS_MOTIVO = {
    "sem_historico_etapa": "rodando pela primeira vez, sem histórico de estimativas",
    "configuracao_mudou": "a configuração que muda o trabalho do item mudou; o histórico anterior não vale",
}


def chave(item: str | None, etapa: str) -> str:
    return f"{item or ''}|{etapa}"


def _payload(estimativa: EstimativaEtapa) -> dict[str, Any]:
    return {
        "etapa": estimativa.etapa,
        "item": estimativa.item,
        "segundos": estimativa.segundos,
        "segundos_por_tarefa": estimativa.segundos_por_tarefa,
        "tarefas_restantes": estimativa.tarefas_restantes,
        "tarefas_origem": estimativa.tarefas_origem,
        "base": None if estimativa.base is None else {"tipo": estimativa.base.tipo, "amostras": estimativa.base.amostras},
        "motivo": estimativa.motivo,
    }


def _do_payload(dados: dict[str, Any]) -> EstimativaEtapa:
    base = dados.get("base")
    return EstimativaEtapa(dados["etapa"], dados.get("item"), dados.get("segundos"),
                           Base(base["tipo"], base["amostras"]) if base else None, dados.get("motivo"),
                           dados.get("segundos_por_tarefa"), dados.get("tarefas_restantes"), dados.get("tarefas_origem"))


class EstimateService:
    def __init__(self, steps: Any, items: Any, plans: Any) -> None:
        self.steps = steps     # SqlAlchemyStepRunStore
        self.items = items     # RecordExecutionItemProgress (Orchestration)
        self.plans = plans     # callable(task_execution_id) -> list[StepPlan]

    def freeze(self, ctx: AttemptTelemetryContextDTO, manifesto: Any, itens: Iterable[str]) -> None:
        """Congela a estimativa das etapas destes itens (e das etapas sem item) na tentativa."""
        if not manifesto.steps:
            return
        corte = ctx.execution_created_at or datetime.now(timezone.utc)
        ja = self.steps.snapshot(ctx.execution_attempt_id)
        historico = self.steps.history(manifesto.automation_id, [s.chave for s in manifesto.steps])
        restantes = self._restantes(ctx.task_execution_id)
        entradas: dict[str, dict[str, Any]] = {}
        alvos: list[str | None] = [None, *itens]
        for etapa in manifesto.steps:
            for item in alvos:
                if (item is None) == etapa.por_item:
                    continue
                k = chave(item, etapa.chave)
                if k in ja or k in entradas:
                    continue
                assinatura = (self.items.work_signature(ctx.task_execution_id, item) or "") if item else ""
                estimativa = estimar_etapa(etapa, manifesto.automation_id, item, assinatura, historico, corte,
                                           restantes.get(k) if etapa.por_tarefa else None, ctx.execution_id)
                entradas[k] = _payload(estimativa)
        self.steps.freeze(execution_attempt_id=ctx.execution_attempt_id, execution_id=ctx.execution_id,
                          task_execution_id=ctx.task_execution_id, cutoff=corte, entries=entradas)

    def _restantes(self, task_execution_id: str) -> dict[str, int]:
        """Na retomada, só o que falta: previstas menos as já feitas por outras tentativas."""
        return {chave(p.item_key, p.step_key): max(p.planned_tasks - p.completed_tasks, 0)
                for p in self.plans(task_execution_id) if p.planned_tasks is not None}


def estimativa_do_job(steps_manifest: tuple[EtapaDeclarada, ...], snapshot: dict[str, dict[str, Any]],
                      itens: list[str]) -> tuple[list[EstimativaEtapa], Any]:
    """Regra 10: as etapas do job (na ordem do manifesto, por item) e a soma."""
    partes: list[EstimativaEtapa] = []
    for etapa in steps_manifest:
        alvos = itens if etapa.por_item else [None]
        for item in alvos:
            dados = snapshot.get(chave(item, etapa.chave))
            partes.append(_do_payload(dados) if dados else EstimativaEtapa(etapa.chave, item, None, None, "sem_historico_etapa"))
    return partes, somar(partes)


def resumo_de_tempos(historico: list[Any], etapas: tuple[EtapaDeclarada, ...], item: str) -> list[dict[str, Any]]:
    """Tempo por etapa de UM item (regra 1): execuções, típico, por tarefa, último e quando.
    Etapas sem item mostram o histórico da automação (regra 5) e dizem isso."""
    saida = []
    for etapa in etapas:
        do_alvo = [m for m in historico if m.etapa == etapa.chave and (not etapa.por_item or m.item == item)]
        concluidas = execucoes_concluidas(do_alvo)
        ultimas = concluidas[:AMOSTRAS]
        taxas = [s / t for _, s, t in ultimas if t > 0]
        saida.append({
            "etapa": etapa.chave,
            "nome": etapa.nome,
            "base": "item" if etapa.por_item else "automacao",
            "execucoes": len(concluidas),
            "tipico_s": median(s for _, s, _ in ultimas) if ultimas else None,
            "por_tarefa_s": median(taxas) if etapa.por_tarefa and taxas else None,
            "ultimo_s": concluidas[0][1] if concluidas else None,
            "quando": concluidas[0][0].isoformat() if concluidas else None,
            "falhas": len({m.execution_id for m in do_alvo if m.situacao in ("erro", "interrompida")}),
        })
    return saida


def _motivo(estimativa: EstimativaEtapa) -> str | None:
    return TEXTOS_MOTIVO.get(estimativa.motivo or "", estimativa.motivo)


def _soma_payload(soma: Any) -> dict[str, Any]:
    return {"segundos": soma.segundos, "sem_base": soma.sem_base, "total": soma.total, "completa": soma.completa}


class GetExecutionEstimate:
    """Estimativa e tempo real por etapa, item, job e execução (regras 9, 10 e 11)."""

    def __init__(self, jobs: Any, manifests: Any, steps: Any, items: Any) -> None:
        self.jobs = jobs
        self.manifests = manifests
        self.steps = steps
        self.items = items

    def execute(self, execution_id: str) -> dict[str, Any]:
        medidas = self.steps.for_execution(execution_id)
        jobs_saida, somas = [], []
        for job in self.jobs.jobs(execution_id):
            manifesto = self.manifests.get(job["automation_version_id"])
            if manifesto is None or not manifesto.steps:
                continue
            itens = self.items.item_keys(job["job_id"])
            snapshot = self.steps.snapshot(job["tentativa_id"]) if job["tentativa_id"] else {}
            planos = {chave(p.item_key, p.step_key): p for p in self.items.plans(job["job_id"])}
            partes, _ = estimativa_do_job(manifesto.steps, snapshot, itens)
            nomes = {s.chave: s for s in manifesto.steps}
            linhas, ajustadas = [], []
            for parte in partes:
                k = chave(parte.item, parte.etapa)
                do_job = [m for m in medidas if m.task_execution_id == job["job_id"] and m.step_key == parte.etapa
                          and m.item_key == parte.item]
                plano = planos.get(k)
                anteriores = sum(m.tasks for m in do_job if m.execution_attempt_id != job["tentativa_id"])
                estimativa = parte
                if parte.segundos_por_tarefa is not None and plano and plano.planned_tasks is not None:
                    # Tarefas declaradas pela automação nesta tentativa: o ritmo segue o congelado.
                    restantes = max(plano.planned_tasks - anteriores, 0)
                    estimativa = EstimativaEtapa(parte.etapa, parte.item, parte.segundos_por_tarefa * restantes,
                                                 parte.base, parte.motivo, parte.segundos_por_tarefa, restantes, "declaradas")
                ajustadas.append(estimativa)
                ultima = max(do_job, key=lambda m: m.start_sequence, default=None) if do_job else None
                real = sum(float(m.net_seconds or 0) for m in do_job if m.status != "executando") if do_job else None
                linhas.append({
                    "etapa": parte.etapa,
                    "nome": nomes[parte.etapa].nome,
                    "item": parte.item,
                    "por_tarefa": nomes[parte.etapa].por_tarefa,
                    "estimativa_s": estimativa.segundos,
                    "segundos_por_tarefa": estimativa.segundos_por_tarefa,
                    "tarefas_restantes": estimativa.tarefas_restantes,
                    "tarefas_origem": estimativa.tarefas_origem,
                    "base": None if estimativa.base is None else {
                        "tipo": estimativa.base.tipo, "amostras": estimativa.base.amostras, "texto": estimativa.base.texto()},
                    "motivo": estimativa.motivo,
                    "motivo_texto": _motivo(estimativa),
                    "situacao": ultima.status if ultima else "pendente",
                    "inicio": ultima.started_at.isoformat() if ultima else None,
                    "real_s": real,
                    "tarefas_previstas": plano.planned_tasks if plano else None,
                    "tarefas_feitas": plano.completed_tasks if plano else 0,
                })
            soma = somar(ajustadas)
            somas.append(soma)
            jobs_saida.append({**job, "itens": itens, "etapas": linhas, "estimativa": _soma_payload(soma)})
        return {"execution_id": execution_id, "jobs": jobs_saida, "estimativa": _soma_payload(somar(somas))}


class GetItemStepTimes:
    """Histórico e tempos por etapa de um item, numa automação (nunca mistura itens)."""

    def __init__(self, steps: Any) -> None:
        self.steps = steps

    def execute(self, automation_id: int, item: str, etapas: tuple[EtapaDeclarada, ...]) -> list[dict[str, Any]]:
        historico = self.steps.history(automation_id, [e.chave for e in etapas])
        return resumo_de_tempos(historico, etapas, item)


class QueueEstimates:
    """Estimativas para a fila (Dispatch): job esperando e o que falta do job rodando."""

    def __init__(self, steps: Any, manifests: Any, plans: Any, attempts_of_job: Any) -> None:
        self.steps = steps
        self.manifests = manifests
        self.plans = plans                      # task_execution_id -> list[StepPlan]
        self.attempts_of_job = attempts_of_job  # task_execution_id -> id da tentativa mais recente | None

    def estimar_job(self, automation_version_id: int, itens: list[dict[str, Any]], corte: datetime, job_id: str) -> Any:
        """Soma das etapas do job (regra 10), com a base até ``corte``. Sem etapas declaradas: sem previsão."""
        manifesto = self.manifests.get(automation_version_id)
        if manifesto is None or not manifesto.steps:
            return somar([EstimativaEtapa("execucao", None, None, None, "sem_historico_etapa")])
        historico = self.steps.history(manifesto.automation_id, [s.chave for s in manifesto.steps])
        restantes = {chave(p.item_key, p.step_key): max(p.planned_tasks - p.completed_tasks, 0)
                     for p in self.plans(job_id) if p.planned_tasks is not None}
        partes = []
        for etapa in manifesto.steps:
            alvos = itens if etapa.por_item else [None]
            for item in alvos:
                chave_item = item["chave"] if item else None
                partes.append(estimar_etapa(
                    etapa, manifesto.automation_id, chave_item, item["assinatura"] if item else "", historico, corte,
                    restantes.get(chave(chave_item, etapa.chave)) if etapa.por_tarefa else None))
        return somar(partes)

    def nomes_das_etapas(self, automation_version_id: int) -> dict[str, str]:
        manifesto = self.manifests.get(automation_version_id)
        return {s.chave: s.nome for s in manifesto.steps} if manifesto is not None else {}

    def restante(self, execution_id: str, job_id: str, desde: datetime | None, agora: datetime) -> tuple[float | None, str | None]:
        tentativa = self.attempts_of_job(job_id)
        snapshot = self.steps.snapshot(tentativa) if tentativa else {}
        valores = [d.get("segundos") for d in snapshot.values()]
        if not valores or any(v is None for v in valores):
            return None, "aguardando_job_sem_previsao"
        decorrido = max((agora - (desde or agora)).total_seconds(), 0.0)
        total = float(sum(valores))
        if decorrido > total:
            return None, "acima_da_estimativa"
        return total - decorrido, None
