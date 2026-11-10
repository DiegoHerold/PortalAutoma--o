"""Pedido de execução para a fila, job perdido e conclusão da tentativa direta.

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


class FilaError(ValueError):
    pass


class QueueStore(Protocol):
    def add_job_or_existing(self, task: TaskExecutionDTO) -> tuple[str, bool]: ...
    def create_pending_items(self, *, execution_id: str, task_execution_id: str, automation_id: int,
                             itens: list[dict[str, Any]]) -> None: ...
    def reset_progress(self, task_execution_id: str) -> None: ...
    def last_attempt(self, task_execution_id: str) -> Any: ...


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
                prioridade: int, solicitante: str | None, now: datetime) -> dict[str, Any]:
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
                    organization_id=None, input={"parametros": parametros, "itens": chaves}, result=None,
                    correlation_id=None, idempotency_key=None, created_at=now))
                execucao_criada = True
            tarefa = TaskExecutionDTO(
                id=f"tsk_{uuid4().hex}", execution_id=execution_id, automation_version_id=automation_version_id,
                status="queued", priority=prioridade, parameters=parametros, input={"itens": chaves_grupo},
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
        self.tasks.save(replace(tarefa, status=status, completed_at=at,
                                failure_summary=resumo if status != "succeeded" else None))
        irmas = self.tasks.list_for_execution(tarefa.execution_id)
        finais = [t.status if t.id != tarefa.id else status for t in irmas]
        if all(s in TERMINAIS for s in finais):
            execucao = self.executions.get(tarefa.execution_id)
            if execucao is not None:
                geral = "succeeded" if all(s == "succeeded" for s in finais) else (
                    "failed" if all(s != "succeeded" for s in finais) else "partially_succeeded")
                self.executions.save(replace(execucao, status=geral, completed_at=at))


class MarcarTentativasDiretasPerdidas:
    """Instância direta sem sinal com job rodando: o job vira perdido e espera uma pessoa.
    A trava de tela fica (a máquina pode ainda estar rodando a automação)."""

    def __init__(self, sem_sinal: Any, tasks: Any, attempts: Any, locks: Any) -> None:
        self.sem_sinal = sem_sinal
        self.tasks = tasks
        self.attempts = attempts
        self.locks = locks

    def execute(self, now: datetime) -> int:
        perdidos = 0
        for attempt_id, task_id in self.sem_sinal(now):
            tentativa = self.attempts.get(attempt_id)
            tarefa = self.tasks.get(task_id)
            if tentativa is None or tarefa is None:
                continue
            self.attempts.save(replace(tentativa, status="lost", completed_at=now, error_code="DIRECT_INSTANCE_SILENT",
                                       error_message="A instância direta parou de dar sinal."))
            self.locks.release_for_attempt(attempt_id, now, "attempt_lost", keep_scopes=("maquina_tela",))
            self.tasks.save(replace(tarefa, status="lost", lost_at=now,
                                    failure_summary="Máquina sem sinal: job perdido, aguardando decisão."))
            perdidos += 1
        return perdidos
