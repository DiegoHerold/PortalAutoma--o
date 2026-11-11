"""
Biason - Libera reservas de pool presas (o motivo real do "pending" eterno)

diagnose_pending.py confirmou a causa: toda execucao nova e rejeitada com
POOL_UNAVAILABLE (pool_type=background) porque available_pool_units fica
sempre 0 - o pool de background (BackgroundPoolSize=2) esta com as 2 vagas
ocupadas por RESERVAS (ResourceReservationRecord) presas de alguma execucao
anterior que nunca foi liberada.

Essas reservas so sao liberadas como efeito colateral de duas rotinas
(modules/orchestration/application/use_cases/resilience.py):
  - ForceCancelExecutionAttempt: so age em cima de uma CancellationRequest
    ja existente e "devida" - nao varre reservas presas sozinha.
  - DetectLostAttempts: so age se a heranca de heartbeat/lease indicar que
    o attempt esta "perdido" pelos criterios dela.
Nenhuma delas necessariamente pega uma reserva organica presa (ex.: de uma
execucao que ficou em "offered"/"accepted" e o Agent.Service que deveria
processa-la foi reiniciado no meio - exatamente o que fizemos varias vezes
nesta sessao com "certification stop/start").

Este script:
  1) Consulta o banco DIRETO (mesma engine do backend, via SessionLocal) pra
     achar as reservas presas do agente informado.
  2) Para cada execucao dona dessas reservas, chama POST /executions/{id}/cancel
     pela API do Portal (o mesmo endpoint que o botao "cancelar" usaria) -
     isso libera a reserva imediatamente se o attempt ainda estiver em
     created/offered/accepted (o caso mais provavel aqui), ou manda um
     comando de cancelamento gracioso pro Agent caso contrario.

Uso (rode a partir de backend/ com o virtualenv):
  .venv/Scripts/python -u -m tools.certification.free_stuck_pool agt_CI0ZDEZtkhgWt1INDFEj7Bh
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

from infrastructure.database import SessionLocal
from modules.dispatch.infrastructure.orm.models import ResourceReservationRecord
from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
from tools.certification.api_client import PortalApiClient

PORTAL_API_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")

ACTIVE_RESERVATION_STATUSES = ("pending", "active", "reserved", "converted")


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python -m tools.certification.free_stuck_pool <agent_id> [pool_type]")
        return 2
    agent_id = sys.argv[1]
    pool_type = sys.argv[2] if len(sys.argv) > 2 else "background"

    print(f"Procurando reservas presas para agent_id={agent_id}, pool_type={pool_type}...")
    with SessionLocal() as db:
        rows = db.execute(
            select(ResourceReservationRecord, TaskExecutionRecord.execution_id)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ResourceReservationRecord.task_execution_id)
            .where(
                ResourceReservationRecord.agent_id == agent_id,
                ResourceReservationRecord.pool_type == pool_type,
                ResourceReservationRecord.status.in_(ACTIVE_RESERVATION_STATUSES),
            )
        ).all()

    if not rows:
        print("Nenhuma reserva presa encontrada - o pool ja deveria estar livre. "
              "Se ainda estiver dando POOL_UNAVAILABLE, o problema e outro (rode diagnose_pending.py de novo).")
        return 0

    print(f"\n{len(rows)} reserva(s) presa(s) encontrada(s):")
    execution_ids: set[str] = set()
    for reservation, execution_id in rows:
        print(f"  - reservation={reservation.id} status={reservation.status} "
              f"task_execution={reservation.task_execution_id} execution={execution_id} "
              f"reserved_at={reservation.reserved_at} expires_at={reservation.expires_at}")
        execution_ids.add(execution_id)

    print(f"\nCancelando {len(execution_ids)} execucao(oes) dona(s) dessas reservas via API do Portal...")
    client = PortalApiClient(PORTAL_API_URL)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    for execution_id in execution_ids:
        try:
            result = client.cancel_execution(execution_id, reason="biason_free_stuck_pool: reserva de pool presa, liberando manualmente")
            print(f"  - {execution_id}: {result}")
        except Exception as exc:  # noqa: BLE001 - queremos ver qualquer erro e seguir pras outras
            print(f"  - {execution_id}: ERRO ao cancelar - {exc}")

    client.close()

    print("\nSe alguma execucao acima nao voltou status='cancelled' na hora (ficou 'cancelling'), "
          "o Agent recebeu um comando de cancelamento gracioso e pode levar ate ~120s pra liberar de vez "
          "(o housekeeping force_cancel_execution_attempts cuida disso sozinho). "
          "Rode demo_all_runtimes.py de novo depois.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
