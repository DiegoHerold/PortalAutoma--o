"""Projeção dos eventos da automação em itens, etapas medidas, pausas e estimativas.

Roda na mesma transação que grava os eventos. As durações usam o ``occurred_at`` do
próprio evento da automação (o mesmo relógio no início e no fim da etapa), igual nos
dois modos de conexão: é isso que dá o mesmo histórico no modo agente e no direto.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from modules.telemetry.application.dto import AttemptTelemetryContextDTO, ExecutionEventDTO
from modules.telemetry.domain.estimativas import duracao_liquida
from modules.telemetry.domain.states import ExecutionEventType


class ItemProgressPort(Protocol):
    """Caso de uso de Orchestration (RecordExecutionItemProgress)."""

    def item_started(self, **kwargs: Any) -> None: ...
    def item_finished(self, **kwargs: Any) -> None: ...
    def item_attention(self, **kwargs: Any) -> None: ...
    def work_signature(self, task_execution_id: str, item_key: str | None) -> str | None: ...
    def item_keys(self, task_execution_id: str) -> list[str]: ...
    def step_planned(self, **kwargs: Any) -> None: ...
    def tasks_completed(self, **kwargs: Any) -> None: ...


def assinatura_trabalho(configuracao: dict[str, Any] | None, atributos: tuple[str, ...] | None) -> str:
    """Regra 6: só os atributos que o manifesto declara como "afetam o trabalho".
    Sem declaração de itens no manifesto, vale toda a configuração enviada."""
    configuracao = configuracao or {}
    if atributos is not None:
        configuracao = {chave: configuracao.get(chave) for chave in atributos}
    texto = json.dumps(configuracao, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _quando(evento: dict[str, Any]) -> datetime:
    valor = datetime.fromisoformat(str(evento["occurred_at"]).replace("Z", "+00:00"))
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


class ProjectAutomationEvents:
    def __init__(self, steps: Any, items: ItemProgressPort, manifests: Any, estimates: Any,
                 concluir_direta: Any = None) -> None:
        self.concluir_direta = concluir_direta  # Orchestration: ConcluirTentativaDireta.execute
        self.steps = steps
        self.items = items
        self.manifests = manifests
        self.estimates = estimates

    def execute(self, context: AttemptTelemetryContextDTO, events: list[ExecutionEventDTO]) -> None:
        automacao = [e for e in events if e.event_type == ExecutionEventType.AUTOMATION_EVENT.value]
        if not automacao or context.automation_version_id is None:
            return
        manifesto = self.manifests.get(context.automation_version_id)
        if manifesto is None:
            return
        for registro in sorted(automacao, key=lambda e: e.payload["sequence"]):
            self._projetar(context, manifesto, registro.payload)

    def _projetar(self, ctx: AttemptTelemetryContextDTO, manifesto: Any, evento: dict[str, Any]) -> None:
        tipo, dados, quando, seq = evento["type"], evento["payload"], _quando(evento), int(evento["sequence"])
        task, tentativa = ctx.task_execution_id, ctx.execution_attempt_id

        if tipo == "execucao.iniciada":
            self.estimates.freeze(ctx, manifesto, self.items.item_keys(task))
        elif tipo == "execucao.concluida":
            # No modo agente quem encerra a tentativa é o Agent (execution.completed); no direto, o evento.
            if ctx.executor_type == "direct" and self.concluir_direta is not None:
                self.concluir_direta(attempt_id=tentativa, situacao=dados["situacao"], resumo=dados.get("resumo"), at=quando)
        elif tipo == "item.iniciado":
            assinatura = assinatura_trabalho(dados.get("configuracao"), manifesto.work_attributes)
            self.items.item_started(execution_id=ctx.execution_id, task_execution_id=task,
                                    automation_id=manifesto.automation_id, item_key=dados["item"],
                                    label=dados.get("rotulo"), group_key=dados.get("grupo"),
                                    configuration=dados.get("configuracao") or {}, work_signature=assinatura, at=quando)
            self.estimates.freeze(ctx, manifesto, [dados["item"]])
        elif tipo == "item.concluido":
            self.items.item_finished(task_execution_id=task, item_key=dados["item"], status=dados["situacao"],
                                     summary=dados.get("resumo"), at=quando)
        elif tipo == "atencao":
            self.items.item_attention(task_execution_id=task, item_key=dados["item"],
                                      attention={k: dados[k] for k in ("motivo", "tabela", "acoes") if k in dados})
        elif tipo == "etapa.iniciada":
            item = dados.get("item")
            self.steps.open(
                run_id=f"stp_{uuid4().hex}", execution_id=ctx.execution_id, task_execution_id=task,
                execution_attempt_id=tentativa, automation_id=manifesto.automation_id,
                automation_version_id=ctx.automation_version_id, step_key=dados["etapa"], item_key=item,
                work_signature=self.items.work_signature(task, item) or "",
                planned_tasks=dados.get("tarefas_previstas"), started_at=quando, machine_id=ctx.machine_id,
                executor_type=ctx.executor_type, start_sequence=seq,
            )
            if "tarefas_previstas" in dados:
                self.items.step_planned(task_execution_id=task, item_key=item, step_key=dados["etapa"],
                                        planned_tasks=dados["tarefas_previstas"])
        elif tipo == "etapa.concluida":
            item = dados.get("item")
            aberta = self.steps.open_run(tentativa, dados["etapa"], item)
            if aberta is None:
                return  # conclusão sem início (evento perdido): a etapa não entra no histórico
            liquida, pausada = duracao_liquida(aberta.started_at, quando, self.steps.pauses(tentativa))
            bruta = max((quando - aberta.started_at).total_seconds(), 0.0)
            tarefas = int(dados.get("tarefas") or 0)
            self.steps.close(aberta, status=dados["situacao"], tasks=tarefas, completed_at=quando,
                             gross=bruta, paused=pausada, net=liquida)
            self.items.tasks_completed(task_execution_id=task, item_key=item, step_key=dados["etapa"], tasks=tarefas)
        elif tipo == "pausa.iniciada":
            self.steps.pause_started(execution_attempt_id=tentativa, start_sequence=seq, reason=dados["motivo"],
                                     item_key=dados.get("item"), at=quando)
        elif tipo == "pausa.concluida":
            self.steps.pause_ended(execution_attempt_id=tentativa, reason=dados["motivo"], at=quando)
