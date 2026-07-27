# Fleet

Ownership: Agents, AgentInstances, registro, capabilities, perfil da maquina,
capacidade, sessao interativa, pools, diagnosticos, atualizacoes e politicas
administrativas do Agent.

Legado a migrar:

- `app/models/worker.py`
- `app/services/worker_service.py`
- `app/services/agent_gateway_service.py`
- `app/api/v1/endpoints/workers.py`
- `app/api/v1/endpoints/agents.py`

`Worker` e adaptador temporario de `Agent`.

