# Fleet

Ownership: Agents, AgentInstances, registro, capabilities, perfil da maquina,
capacidade, sessao interativa, pools, diagnosticos, atualizacoes e politicas
administrativas do Agent.

Legado a migrar:

- `app/models/worker.py` (classe ORM antiga; tabela `workers` já é a mesma
  tabela física de `modules.fleet`, via `extend_existing` — remover a classe
  antiga é seguro, mas fica para o lote de limpeza de models compartilhados).

Removido (Fase de remoção do legado): `app/services/worker_service.py`,
`app/services/agent_gateway_service.py`, `app/api/v1/endpoints/workers.py`,
`app/api/v1/endpoints/agents.py` — sem consumidores restantes; `/workers` e
`/agents` já são servidos integralmente por `modules/fleet` e pelo Agent
Gateway oficial (`backend/gateway/agent_gateway`).

`Worker` e adaptador temporario de `Agent`.

