"""Pedido de execução para a fila, job perdido, parar, continuar e conclusão da tentativa direta.

Orchestration é dono de execuções, jobs (TaskExecution) e tentativas. Regras da fila
(ordem, máquina, previsão) ficam em ``modules.dispatch.domain.fila``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from modules.dispatch.domain.fila import agrupar, chave_de_duplicata, maquina_da_retomada
from modules.orchestration.application.dto import ExecutionDTO, TaskExecutionDTO
from modules.orchestration.application.use_cases.executions import (
    _default_timeout_policy,
    _requirements_snapshot,
    _retry_policy,
)

SITUACAO_PARA_STATUS = {"ok": "succeeded", "atencao": "succeeded", "erro": "failed", "interrompida": "cancelled"}
TERMINAIS = {"succeeded", "failed", "cancelled", "timed_out", "skipped"}
# Item que não precisa rodar de novo ao continuar: deu certo, foi ignorado ou espera uma pessoa.
ITENS_FEITOS = {"ok", "ignorado", "atencao"}
MODOS_DE_PARAR = ("apos_item", "agora")
COMANDO_DO_MODO = {"apos_item": "parar_apos_item", "agora": "cancelar"}


class FilaError(ValueError):
    pass


class QueueStore(Protocol):
    def add_job_or_existing(self, task: TaskExecutionDTO) -> tuple[str, bool]: ...
    def create_pending_items(self, *, execution_id: str, task_execution_id: str, automation_id: int,
                             itens: list[dict[str, Any]]) -> None: ...
    def reset_progress(self, task_execution_id: str) -> None: ...
    def last_attempt(self, task_execution_id: str) -> Any: ...
    def itens_da_execucao(self, execution_id: str) -> list[dict[str, Any]]: ...


def situacao_geral(finais: list[str]) -> str:
    """Situação da execução quando todos os jobs terminaram. Parada por uma pessoa conta como
    cancelada (e não como falha), a menos que algum job tenha dado certo."""
    if all(s == "succeeded" for s in finais):
        return "succeeded"
    if any(s == "succeeded" for s in finais):
        return "partially_succeeded"
    return "cancelled" if any(s == "cancelled" for s in finais) else "failed"


def fechar_execucao(executions: Any, tasks: Any, execution_id: str, at: datetime) -> str | None:
    """Fecha a execução quando o último job terminou. Devolve a situação, ou None se algum segue."""
    finais = [t.status for t in tasks.list_for_execution(execution_id)]
    if not finais or not all(s in TERMINAIS for s in finais):
        return None
    execucao = executions.get(execution_id)
    if execucao is None:
        return None
    geral = situacao_geral(finais)
    executions.save(replace(execucao, status=geral, completed_at=execucao.completed_at or at))
    return geral


@dataclass(frozen=True)
class JobPedido:
    job_id: str
    itens: list[str]
    existente: bool


def assinatura(configuracao: dict[str, Any] | None, atributos: tuple[str, ...] | None) -> str:
    """Igual à da projeção (Telemetry): só os atributos que mudam o trabalho."""
    configuracao = configuracao or {}
    if atributos is not None:
        configuracao = {chave: configuracao.get(chave) for chave in atributos}
    texto = json.dumps(configuracao, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class EnfileirarExecucao:
    def __init__(self, executions: Any, versions: Any, store: QueueStore) -> None:
        self.executions = executions
        self.versions = versions
        self.store = store

    def execute(self, *, automation_version_id: int, itens: list[dict[str, Any]], parametros: dict[str, Any],
                prioridade: int, solicitante: str | None, now: datetime, continua_de: str | None = None) -> dict[str, Any]:
        versao = self.versions.get_published_snapshot(automation_version_id)
        if versao is None:
            raise FilaError("A versão não está publicada com pacote e runtime: não pode entrar na fila.")
        chaves = [str(i.get("chave") or "").strip() for i in itens]
        if any(not c for c in chaves) or len(set(chaves)) != len(chaves):
            raise FilaError("Cada item precisa de uma chave, sem repetição.")
        manifesto_itens = (versao.manifest or {}).get("items") if isinstance(versao.manifest, dict) else None
        atributos = tuple(manifesto_itens.get("work_attributes") or ()) if isinstance(manifesto_itens, dict) else None

        execution_id = f"exe_{uuid4().hex}"
        grupos = agrupar(itens) if itens else [[]]
        pedidos: list[JobPedido] = []
        execucao_criada = False
        for grupo in grupos:
            chaves_grupo = [str(i["chave"]) for i in grupo]
            dedup = chave_de_duplicata(versao.automation_id, chaves_grupo, parametros)
            if not execucao_criada:
                self.executions.add(ExecutionDTO(
                    id=execution_id, type="automation", origin="manual", status="queued", requested_by=solicitante,
                    organization_id=None, input={"parametros": parametros, "itens": chaves,
                                                 **({"continua_de": continua_de} if continua_de else {})}, result=None,
                    correlation_id=None, idempotency_key=None, created_at=now))
                execucao_criada = True
            tarefa = TaskExecutionDTO(
                id=f"tsk_{uuid4().hex}", execution_id=execution_id, automation_version_id=automation_version_id,
                status="queued", priority=prioridade, parameters=parametros,
                # Retrato dos itens no pedido: mudar o cadastro depois não altera o job na fila (seção 6.5).
                input={"itens": chaves_grupo, "dados_dos_itens": [
                    {campo: i.get(campo) for campo in ("chave", "rotulo", "grupo", "configuracao", "atributos", "retomada")
                     if campo != "retomada" or i.get("retomada")}
                    for i in grupo]},
                result=None, retry_policy=_retry_policy(versao),
                timeout_policy=versao.timeout_policy or _default_timeout_policy(versao.timeout_seconds),
                created_at=now, queued_at=now,
                requirements_snapshot=_requirements_snapshot(versao, execution_id, prioridade, None),
                group_key=str(grupo[0].get("grupo") or grupo[0]["chave"]) if grupo else None,
                dedup_key=dedup, enqueue_batch_id=execution_id, enqueued_at=now, pool=versao.execution_mode,
            )
            job_id, criado = self.store.add_job_or_existing(tarefa)
            if criado and grupo:
                self.store.create_pending_items(
                    execution_id=execution_id, task_execution_id=job_id, automation_id=versao.automation_id,
                    itens=[{**i, "assinatura": assinatura(i.get("configuracao"), atributos)} for i in grupo])
            pedidos.append(JobPedido(job_id, chaves_grupo, existente=not criado))
        novos = [p for p in pedidos if not p.existente]
        return {
            "execution_id": execution_id if novos else None,
            "jobs": [{"job_id": p.job_id, "itens": p.itens, "existente": p.existente} for p in pedidos],
        }


class DecidirJobPerdido:
    """Uma pessoa decide o job perdido: continuar de onde parou ou recomeçar do zero."""

    def __init__(self, tasks: Any, store: QueueStore, locks: Any) -> None:
        self.tasks = tasks
        self.store = store
        self.locks = locks

    def execute(self, *, job_id: str, decisao: str, estado_central: bool, now: datetime) -> TaskExecutionDTO:
        tarefa = self.tasks.get(job_id)
        if tarefa is None:
            raise LookupError("Job não encontrado.")
        if tarefa.status != "lost":
            raise FilaError("Só um job perdido espera essa decisão.")
        if decisao not in ("continuar", "recomecar"):
            raise FilaError("Escolha continuar ou recomecar.")
        ultima = self.store.last_attempt(job_id)
        if ultima is not None:
            self.locks.release_for_attempt(ultima.id, now, f"job_perdido_{decisao}")
        maquina = maquina_da_retomada(getattr(ultima, "machine_id", None), estado_central) if decisao == "continuar" else None
        if decisao == "recomecar":
            self.store.reset_progress(job_id)
        return self.tasks.save(replace(tarefa, status="queued", lost_at=None, required_machine_id=maquina,
                                       queued_at=now, failure_summary=None))


class ConcluirTentativaDireta:
    """Fim declarado pela automação no modo direto (``execucao.concluida``)."""

    def __init__(self, executions: Any, tasks: Any, attempts: Any, locks: Any) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.locks = locks

    def execute(self, *, attempt_id: str, situacao: str, resumo: str | None, at: datetime) -> None:
        tentativa = self.attempts.get(attempt_id)
        if tentativa is None or tentativa.executor_type != "direct" or tentativa.status in TERMINAIS:
            return
        status = SITUACAO_PARA_STATUS.get(situacao, "failed")
        self.attempts.save(replace(tentativa, status=status, completed_at=at,
                                   error_message=resumo if status != "succeeded" else None))
        self.locks.release_for_attempt(attempt_id, at, f"tentativa_{status}")
        tarefa = self.tasks.get(tentativa.task_execution_id)
        if tarefa is None:
            return
        if status == "cancelled" and not resumo:
            resumo = "Parada a pedido." if tarefa.status == "cancelling" else None
        self.tasks.save(replace(tarefa, status=status, completed_at=at,
                                failure_summary=resumo if status != "succeeded" else None))
        fechar_execucao(self.executions, self.tasks, tarefa.execution_id, at)


class PararExecucao:
    """Uma pessoa para a execução inteira: ``apos_item`` (termina o item atual e não começa outro)
    ou ``agora`` (interrompe o quanto antes).

    - Job ainda na fila (ou perdido): cancelado na hora, sem passar por máquina nenhuma.
    - Job rodando no modo direto: o comando vai para ``direct_commands`` e a automação o recebe
      pela consulta que ela mesma faz (nenhuma máquina abre porta). ``agora`` deixa o job em
      ``cancelling`` até a automação declarar o fim.
    - Job rodando no modo agente: só ``agora``, pelo cancelamento que já existia (o Agent encerra
      o processo).
    """

    def __init__(self, executions: Any, tasks: Any, store: QueueStore, comandos_diretos: Any, locks: Any,
                 cancelar_no_agent: Any) -> None:
        self.executions = executions
        self.tasks = tasks
        self.store = store
        self.comandos = comandos_diretos
        self.locks = locks
        self.cancelar_no_agent = cancelar_no_agent

    def execute(self, *, execution_id: str, modo: str, motivo: str | None, now: datetime) -> dict[str, Any]:
        if modo not in MODOS_DE_PARAR:
            raise FilaError("Escolha parar depois do item atual (apos_item) ou cancelar agora (agora).")
        tarefas = self.tasks.list_for_execution(execution_id)
        if not tarefas:
            raise LookupError("Execução não encontrada.")
        ativas = [t for t in tarefas if t.status not in TERMINAIS]
        if not ativas:
            raise FilaError("Esta execução já terminou.")
        tentativas = {t.id: self.store.last_attempt(t.id) for t in ativas if t.status in ("running", "cancelling", "ready")}
        no_agent = [t for t in ativas if tentativas.get(t.id) is not None and tentativas[t.id].executor_type != "direct"]
        if no_agent and modo == "apos_item":
            raise FilaError("No modo agente só dá para cancelar agora.")

        resultado = {"execution_id": execution_id, "modo": modo, "canceladas_na_fila": 0, "avisadas": 0, "no_agent": 0}
        for tarefa in ativas:
            tentativa = tentativas.get(tarefa.id)
            if any(t.id == tarefa.id for t in no_agent):
                continue
            if tentativa is None or tarefa.status in ("queued", "lost"):
                if tarefa.status == "lost" and tentativa is not None:
                    self.locks.release_for_attempt(tentativa.id, now, "parada_pedida")
                elif tarefa.status == "lost":
                    ultima = self.store.last_attempt(tarefa.id)
                    if ultima is not None:
                        self.locks.release_for_attempt(ultima.id, now, "parada_pedida")
                self.tasks.save(replace(tarefa, status="cancelled", completed_at=now,
                                        failure_summary="Cancelado antes de começar." if tarefa.status == "queued"
                                        else "Cancelado (o job estava perdido)."))
                resultado["canceladas_na_fila"] += 1
                continue
            tipo = COMANDO_DO_MODO[modo]
            if tipo not in self.comandos.tipos_pedidos(tentativa.id):
                self.comandos.add(command_id=f"cmd_{uuid4().hex}", execution_attempt_id=tentativa.id, command={
                    "protocol_version": "automation-events/1", "command_id": f"cmd_{uuid4().hex}", "type": tipo,
                    "issued_at": now.isoformat(), **({"motivo": motivo[:300]} if motivo else {})})
            if modo == "agora" and tarefa.status == "running":
                self.tasks.save(replace(tarefa, status="cancelling"))
            resultado["avisadas"] += 1
        fechar_execucao(self.executions, self.tasks, execution_id, now)
        if no_agent:
            # O cancelamento do modo agente faz o próprio commit.
            self.cancelar_no_agent(execution_id, motivo)
            resultado["no_agent"] = len(no_agent)
        return resultado


class ContinuarExecucao:
    """Continua uma execução cancelada numa execução nova, só com o que não deu certo.

    Itens que terminaram ok, ignorados ou à espera de uma pessoa são pulados; os pendentes, os
    interrompidos e os que deram erro rodam de novo. Cada item leva ``retomada`` com a situação
    anterior e as etapas que já tinham terminado, para a automação pular se souber.
    """

    def __init__(self, executions: Any, tasks: Any, store: QueueStore, enfileirar: EnfileirarExecucao,
                 etapas_concluidas: Any) -> None:
        self.executions = executions
        self.tasks = tasks
        self.store = store
        self.enfileirar = enfileirar
        self.etapas_concluidas = etapas_concluidas

    def previa(self, execution_id: str) -> dict[str, Any]:
        execucao = self.executions.get(execution_id)
        tarefas = self.tasks.list_for_execution(execution_id)
        if execucao is None or not tarefas:
            raise LookupError("Execução não encontrada.")
        itens = self.store.itens_da_execucao(execution_id)
        refazer = [i for i in itens if i["situacao"] not in ITENS_FEITOS]
        bloqueio = None
        continuada = (execucao.result or {}).get("continuada_em")
        if continuada:
            bloqueio = "Esta execução já foi continuada."
        elif any(t.status not in TERMINAIS for t in tarefas):
            bloqueio = "A execução ainda não terminou: pare primeiro."
        elif not any(t.status == "cancelled" for t in tarefas):
            bloqueio = "Só dá para continuar uma execução que foi cancelada."
        elif itens and not refazer:
            bloqueio = "Todos os itens já deram certo: não há o que continuar."
        return {"execution_id": execution_id, "pode": bloqueio is None, "motivo": bloqueio, "continuada_em": continuada,
                "refazer": [{"chave": i["chave"], "rotulo": i["rotulo"], "situacao": i["situacao"]} for i in refazer],
                "pular": len(itens) - len(refazer), "sem_itens": not itens}

    def execute(self, *, execution_id: str, solicitante: str | None, now: datetime) -> dict[str, Any]:
        previa = self.previa(execution_id)
        if not previa["pode"]:
            raise FilaError(previa["motivo"])
        tarefas = self.tasks.list_for_execution(execution_id)
        dados: dict[str, dict[str, Any]] = {}
        for tarefa in tarefas:
            for item in (tarefa.input or {}).get("dados_dos_itens") or []:
                if isinstance(item, dict) and item.get("chave") is not None:
                    dados[str(item["chave"])] = item
        etapas = self.etapas_concluidas(execution_id) if not previa["sem_itens"] else {}
        itens = [{**{k: v for k, v in (dados.get(i["chave"]) or {"chave": i["chave"], "rotulo": i["rotulo"]}).items()
                     if k != "retomada"},
                  "retomada": {"execucao_anterior": execution_id, "situacao_anterior": i["situacao"],
                               "etapas_concluidas": etapas.get(i["chave"], [])}}
                 for i in previa["refazer"]]
        base = tarefas[0]
        resultado = self.enfileirar.execute(
            automation_version_id=base.automation_version_id, itens=itens, parametros=dict(base.parameters or {}),
            prioridade=base.priority, solicitante=solicitante, now=now, continua_de=execution_id)
        nova = resultado.get("execution_id")
        if nova:
            execucao = self.executions.get(execution_id)
            self.executions.save(replace(execucao, result={**(execucao.result or {}), "continuada_em": nova}))
        return {**resultado, "continua_de": execution_id, "itens": len(itens), "pulados": previa["pular"]}


class EncerrarTentativaDireta:
    """Encerra no Portal uma tentativa direta que não termina sozinha: cancela o job com erro,
    libera a máquina (todas as travas) e revoga o token do job (a automação, se ainda estiver
    viva, recebe 401 e o SDK a cancela). Fecha a execução quando era o último job."""

    def __init__(self, executions: Any, tasks: Any, attempts: Any, locks: Any, revogar_tokens: Any) -> None:
        self.executions = executions
        self.tasks = tasks
        self.attempts = attempts
        self.locks = locks
        self.revogar_tokens = revogar_tokens

    def execute(self, *, attempt_id: str, codigo: str, motivo: str, now: datetime) -> bool:
        tentativa = self.attempts.get(attempt_id)
        if tentativa is None or tentativa.executor_type != "direct" or tentativa.status in TERMINAIS | {"lost"}:
            return False
        tarefa = self.tasks.get(tentativa.task_execution_id)
        self.attempts.save(replace(tentativa, status="cancelled", completed_at=now, error_code=codigo, error_message=motivo))
        self.locks.release_for_attempt(attempt_id, now, codigo.lower())
        self.revogar_tokens(attempt_id, now)
        if tarefa is not None and tarefa.status not in TERMINAIS:
            self.tasks.save(replace(tarefa, status="cancelled", completed_at=now, failure_summary=motivo))
            fechar_execucao(self.executions, self.tasks, tarefa.execution_id, now)
        return True


class MarcarTentativasDiretasPerdidas:
    """Instância direta sem sinal há ``SEM_COMUNICACAO`` com job rodando: a execução é cancelada
    com erro e a máquina liberada (decisão de 12/11/2026). O SDK, na máquina, também se cancela
    depois do mesmo tempo sem o Portal, então nada fica rodando às cegas."""

    MOTIVO = "Sem comunicação com a automação por 2 min: execução cancelada."

    def __init__(self, sem_sinal: Any, encerrar: EncerrarTentativaDireta) -> None:
        self.sem_sinal = sem_sinal
        self.encerrar = encerrar

    def execute(self, now: datetime) -> int:
        return sum(1 for attempt_id, _task_id in self.sem_sinal(now)
                   if self.encerrar.execute(attempt_id=attempt_id, codigo="DIRECT_INSTANCE_SILENT", motivo=self.MOTIVO, now=now))
