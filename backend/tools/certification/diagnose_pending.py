"""
Biason - Diagnostico de execucao presa em "pending"

As 4 execucoes de demo_all_runtimes.py ficam pendentes pra sempre (nunca
chegam nem a ser oferecidas ao Agent, mesmo com o Agent aparecendo "online"
e o worker do Celery rodando normalmente) - isso so pode ser um agente
CANDIDATO sendo rejeitado pelo agendador do Portal antes mesmo de tentar
falar com o Agent de verdade.

Este script le a MESMA informacao que o agendador usa pra decidir (via
GET /executions/{id}/dispatch) - o historico de "dispatch decisions", uma
por rodada do agendador (schedule_ready_tasks, a cada ~5s), com a lista de
agentes candidatos avaliados e o motivo EXATO da rejeicao de cada um
(reject_reason/reject_details - a mesma logica de
FindEligibleAgents._apply_filters em modules/dispatch/application/
use_cases/scheduler.py: AGENT_OFFLINE, RESOURCE_SNAPSHOT_EXPIRED,
CAPABILITY_UNAVAILABLE, POOL_UNAVAILABLE, RUNTIME_UNAVAILABLE, etc). Isso
mostra o motivo real em vez de ficar adivinhando.

Uso (rode a partir de backend/ com o virtualenv, com os execution_id que
ainda estao "pending" - pegue do resumo do demo_all_runtimes.py):
  .venv/Scripts/python -u -m tools.certification.diagnose_pending <execution_id> [<execution_id> ...]
"""

from __future__ import annotations

import json
import os
import sys

from tools.certification.api_client import PortalApiClient

PORTAL_API_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")


def main() -> int:
    execution_ids = sys.argv[1:]
    if not execution_ids:
        print("Uso: python -m tools.certification.diagnose_pending <execution_id> [<execution_id> ...]")
        return 2

    print(f"Conectando ao Portal em {PORTAL_API_URL} ...")
    client = PortalApiClient(PORTAL_API_URL)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print("Login OK.")

    # Regressao encontrada na 1a rodada deste script: o banco tem dezenas de
    # agentes "fixture"/fantasma (agt_worker_1, agt_<hash aleatorio>...),
    # todos desabilitados/offline - parecem sobra de teste de carga/seed. O
    # agendador avalia TODOS eles como candidatos a cada execucao, entao o
    # dump completo (json.dumps de cada decisao) tinha centenas de linhas e
    # cortava exatamente a parte que importa (o candidato do SEU agente
    # real) do buffer do terminal. Agora filtramos so pro(s) agente(s)
    # online de verdade (mesma logica de demo_all_runtimes.py) e so
    # contamos os outros.
    agents = client.list_agents()
    online_agents = [a for a in agents if a.get("connectivity_status") == "online" or a.get("status") == "online"]
    online_ids = {a.get("id") or a.get("agent_id") for a in online_agents}
    print(f"\n{len(agents)} agente(s) no total cadastrados no Portal, {len(online_agents)} marcado(s) como 'online':")
    for a in online_agents:
        print(f"  - {a.get('name', a.get('id'))} (id={a.get('id') or a.get('agent_id')})")
    if len(agents) - len(online_agents) > 5:
        print(f"  ({len(agents) - len(online_agents)} outro(s) agente(s) cadastrados, offline/desabilitados - provavelmente fixture/teste de carga, ignorados abaixo)")

    for execution_id in execution_ids:
        print(f"\n=== {execution_id} ===")
        try:
            result = client.get_execution_dispatch(execution_id)
        except Exception as exc:  # noqa: BLE001 - diagnostico, queremos ver qualquer erro
            print(f"ERRO ao consultar: {exc}")
            continue

        decisions = result.get("decisions", [])
        if not decisions:
            print("Nenhuma dispatch decision registrada ainda para essa execucao.")
            continue

        decision = decisions[-1]  # a mais recente - a mais relevante pro estado atual
        candidates = decision.get("candidates", [])
        print(f"Ultima decisao ({decision.get('created_at')}): decision_reason={decision.get('decision_reason')}, "
              f"{len(candidates)} candidato(s) avaliado(s) no total.")

        found_real_agent = False
        for candidate in candidates:
            if candidate.get("agent_id") in online_ids:
                found_real_agent = True
                print(f"\n  >>> Candidato = SEU agente online ({candidate.get('agent_id')}):")
                print(json.dumps(candidate, indent=4, ensure_ascii=False, default=str))

        if not found_real_agent:
            print(f"\n  >>> ATENCAO: nenhum dos agentes online ({', '.join(online_ids) or '(nenhum)'}) "
                  f"apareceu na lista de {len(candidates)} candidato(s) avaliados para esta execucao! "
                  f"Isso por si so ja seria a causa do 'pending' eterno - o agendador nem chegou a "
                  f"considerar seu agente.")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
