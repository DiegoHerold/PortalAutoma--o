# Fleet e Agent Gateway - Inventario de Migracao

Status: inventario do Prompt 3. `Agent` e `AgentInstance` sao os nomes oficiais.

| Componente legado | Arquivo | Responsabilidade | Conceito oficial correspondente | Contexto de destino | Acao | Endpoint consumidor | Tela afetada | Teste existente |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Worker ORM | `backend/app/models/worker.py` | Identidade, token, heartbeat e slots em uma unica tabela | `Agent`, `AgentConfiguration`, `AgentResourceSnapshot`, `AgentPool` | Fleet | REFACTOR | `/workers`, jobs legados | Workers, Dashboard | arquitetura e compatibilidade |
| WorkerRepository | `backend/app/repositories/worker_repository.py` | CRUD direto de Worker | Adapter de compatibilidade | Fleet infrastructure | KEEP temporario | `/workers` | Workers | indireto |
| WorkerService | `backend/app/services/worker_service.py` | Regras antigas de Worker | Facade Worker -> Agent | Fleet application/API | REPLACE | `/workers` | Workers | arquitetura |
| Agents HTTP legado | `backend/app/api/v1/endpoints/agents.py` | Registro, heartbeat, events e WebSocket | Fleet registration e Agent Gateway | Fleet/Gateway | REFACTOR | Automation Agent legado | N/A | import/backend |
| AgentGatewayService legado | `backend/app/services/agent_gateway_service.py` | Autenticacao por device_token e `execution.assign` | Facade para Fleet; execucao deferida | Gateway/Fleet | REPLACE | `/agents:*`, `/v1/agents:*` | N/A | arquitetura |
| Worker device_token | `backend/app/models/worker.py` | Credencial permanente em texto | `AgentCredential.secret_hash` | Access/Fleet | REPLACE | Agent legado | N/A | registro |
| Worker machine_id | `backend/app/models/worker.py` | Identidade local/fingerprint | `Agent.local_identity`, `machine_fingerprint` | Fleet | MOVE | `/workers` | Workers | migration |
| Worker capabilities_json | `backend/app/models/worker.py` | Lista solta de capabilities | `AgentCapability` tipada | Fleet | REPLACE | `/workers` | Workers | dominio |
| Worker last_payload_json | `backend/app/models/worker.py` | Mistura heartbeat, status e dados brutos | snapshots e payload de compatibilidade | Fleet | REFACTOR | `/workers` | Detail Worker | compatibilidade |
| Worker status unico | `backend/app/core/constants.py` | `online/offline/busy/disabled` | conectividade, administracao, saude, ocupacao | Fleet | REPLACE | `/workers` | Badges | frontend |
| WebSocket antigo `/agents/ws` | `backend/app/api/v1/endpoints/agents.py` | Entrega de execucao e resposta | `/agent-gateway/connect` | Gateway | REPLACE | Automation Agent | N/A | gateway |
| Job task worker simulado | `backend/app/tasks/job_tasks.py` | Simula execucao local por Worker | Execution futura | Orchestration/Dispatch | DEFER | Jobs | Jobs/Executions | fora do Prompt 3 |
| Preferences por worker | `backend/app/models/automation_worker_preference.py` | Preferencia manual por executor | Preferencias por Agent futuras | Dispatch/Fleet | DEFER | automations worker-preferences | Automations | existente |
| Realtime broadcaster | `backend/app/services/realtime_service.py` | Atualizacao de UI | Telemetry/Realtime futuro | Telemetry | KEEP temporario | `/ws/executions` | Dashboard | existente |
| AgentCommand persistente | `backend/modules/dispatch/infrastructure/orm/models.py` | Comandos persistentes | `AgentCommand` | Dispatch/Gateway | REFACTOR | Gateway | N/A | arquitetura |
| Contracts Portal-Agent | `contracts/**` | Envelope e tipos de mensagem | Contrato oficial | Gateway | KEEP | Agent Gateway | N/A | arquitetura |

## Legado que permanece

`backend/app/models/worker.py` permanece como tabela de compatibilidade para telas e foreign keys existentes de Jobs/Executions. A substituicao futura e remover o acoplamento de Job/Execution a `worker_id` quando o Prompt 4 mover execucao para `ExecutionAttempt`/`ExecutionOffer`.

`backend/app/tasks/job_tasks.py` ainda contem simulacao de Worker para o fluxo antigo de Jobs. Isso nao foi migrado porque execucao real pertence ao Prompt 4.
