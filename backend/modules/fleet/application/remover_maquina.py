"""Apagar uma máquina do cadastro (ADR-019).

- Com execução rodando nela: não apaga (espere terminar ou pare a execução).
- Com automação, Agent ou job da fila ligados a ela: só apaga com a confirmação de quem pediu,
  depois de ver a lista. As automações ficam sem máquina (a instância direta volta a esperar
  aprovação), o Agent fica sem máquina e os jobs da fila podem ir para outra máquina que sirva.
- A máquina sai das telas e do despacho. O registro fica, marcado como apagado, para o histórico
  das execuções que rodaram nela; o nome fica livre para uma máquina nova.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent


class MaquinaNaoEncontrada(LookupError):
    pass


class MaquinaOcupada(RuntimeError):
    pass


class PrecisaConfirmar(RuntimeError):
    def __init__(self, vinculos: dict[str, Any]) -> None:
        super().__init__("A máquina tem vínculos: confirme para apagar.")
        self.vinculos = vinculos


def tem_vinculos(vinculos: dict[str, Any]) -> bool:
    return bool(vinculos["automacoes"] or vinculos["agents"] or vinculos["fila"])


class RemoverMaquina:
    def __init__(self, maquinas: Any, uso: Any, audit: Any, transaction: Any,
                 agora: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.maquinas = maquinas
        self.uso = uso
        self.audit = audit
        self.transaction = transaction
        self.agora = agora

    def vinculos(self, machine_id: str) -> dict[str, Any]:
        maquina = self.maquinas.obter(machine_id)
        if maquina is None:
            raise MaquinaNaoEncontrada("Máquina não encontrada.")
        return {"maquina": {"id": maquina.id, "nome": maquina.name},
                "automacoes": self.maquinas.instancias_na_maquina(machine_id),
                "agents": self.maquinas.agents_na_maquina(machine_id),
                "fila": self.uso.na_fila_exigindo(machine_id),
                "rodando": self.uso.rodando(machine_id)}

    def execute(self, ator_id: str | None, machine_id: str, *, confirmar: bool) -> dict[str, Any]:
        vinculos = self.vinculos(machine_id)
        if vinculos["rodando"]:
            raise MaquinaOcupada(f"{vinculos['rodando']} execução(ões) rodando nesta máquina: espere terminar ou pare antes.")
        if tem_vinculos(vinculos) and not confirmar:
            raise PrecisaConfirmar(vinculos)
        self.maquinas.desvincular(machine_id)
        liberados = self.uso.liberar(machine_id)
        self.maquinas.marcar_removida(machine_id, self.agora())
        self.audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="user", actor_id=ator_id, action="maquina.removida",
            resource_type="machine", resource_id=machine_id,
            before={"nome": vinculos["maquina"]["nome"],
                    "automacoes": [{"instancia_id": a["instancia_id"], "automation_id": a["automation_id"],
                                    "situacao": a["situacao"]} for a in vinculos["automacoes"]],
                    "agents": [a["id"] for a in vinculos["agents"]]},
            after={"jobs_liberados": liberados, "confirmado": bool(confirmar)}, occurred_at=self.agora()))
        self.transaction.commit()
        return {"id": machine_id, "nome": vinculos["maquina"]["nome"], "automacoes_sem_maquina": len(vinculos["automacoes"]),
                "agents_sem_maquina": len(vinculos["agents"]), "jobs_liberados": liberados}
