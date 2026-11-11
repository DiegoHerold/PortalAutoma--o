"""Casos de uso da retenção por automação (Fase 6).

Governance guarda o prazo e decide o corte; a Telemetria apaga (imagens pelo Storage, logs
no banco). Cada aplicação que apagou algo entra na auditoria, com as contagens.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent
from modules.governance.domain.retencao_por_automacao import RetencaoDaAutomacao, corte, validar


def _evento(ator_tipo: str, ator_id: str | None, acao: str, automation_id: int, depois: dict[str, Any]) -> AuditEvent:
    return AuditEvent(id=f"aud_{uuid4().hex}", actor_type=ator_tipo, actor_id=ator_id, action=acao,
                      resource_type="automation", resource_id=str(automation_id), after=depois,
                      occurred_at=datetime.now(UTC))


class DefinirRetencao:
    def __init__(self, repositorio: Any, audit: Any, transaction: Any) -> None:
        self.repositorio = repositorio
        self.audit = audit
        self.transaction = transaction

    def execute(self, ator: Any, automation_id: int, imagens_dias: int | None, logs_dias: int | None) -> RetencaoDaAutomacao:
        retencao = validar(automation_id, imagens_dias, logs_dias)
        antes = self.repositorio.obter(automation_id)
        self.repositorio.gravar(retencao, str(getattr(ator, "email", None) or getattr(ator, "id", "")))
        self.audit.append(_evento("user", str(getattr(ator, "id", "")) or None, "retencao.definida", automation_id,
                                  {"imagens_dias": imagens_dias, "logs_dias": logs_dias,
                                   "antes": None if antes is None else {"imagens_dias": antes.imagens_dias,
                                                                        "logs_dias": antes.logs_dias}}))
        self.transaction.commit()
        return retencao


class AplicarRetencao:
    """Uma passada: para cada automação com prazo, apaga um lote do que passou do prazo."""

    def __init__(self, repositorio: Any, telemetria: Any, audit: Any, transaction: Any,
                 agora: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.repositorio = repositorio
        self.telemetria = telemetria
        self.audit = audit
        self.transaction = transaction
        self.agora = agora

    def execute(self) -> list[dict[str, Any]]:
        agora = self.agora()
        feito = []
        for retencao in self.repositorio.com_prazo():
            imagens = logs = 0
            corte_imagens = corte(agora, retencao.imagens_dias)
            if corte_imagens is not None:
                imagens = self.telemetria.apagar_imagens(retencao.automation_id, corte_imagens)
            corte_logs = corte(agora, retencao.logs_dias)
            if corte_logs is not None:
                logs = self.telemetria.apagar_logs(retencao.automation_id, corte_logs)
            if imagens or logs:
                resumo = {"imagens": imagens, "linhas_de_log": logs,
                          "imagens_antes_de": corte_imagens.isoformat() if corte_imagens else None,
                          "logs_antes_de": corte_logs.isoformat() if corte_logs else None}
                self.audit.append(_evento("system", None, "retencao.aplicada", retencao.automation_id, resumo))
                feito.append({"automation_id": retencao.automation_id, **resumo})
            self.transaction.commit()
        return feito
