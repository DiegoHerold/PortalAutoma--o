# Plano de Migracao

Status: vigente.

Objetivo: alinhar o codigo ao modelo oficial sem quebrar funcionalidades
existentes.

## Principios

- Nao apagar dados existentes.
- Manter compatibilidade temporaria nos endpoints legados.
- Introduzir adaptadores antes de trocar o modelo persistente.
- Criar migrations reversiveis sempre que possivel.
- Marcar campos antigos como deprecated antes de remover.
- Executar a menor fatia vertical de ponta a ponta antes de avancar para
  fluxos visuais complexos.

## Modelos antigos

- `workers` vira fonte inicial para criar `agents`.
- `workers.agent_id` e mantido como chave externa temporaria.
- `workers.status` deve ser decomposto em conectividade, administrativo, saude
  e ocupacao calculada.
- `jobs` vira adaptador para `executions` e `task_executions`.
- `executions` legado vira adaptador para `execution_attempts`.

## Estrutura atual e alvo

Atual:

```text
backend/app/
  api/
  core/
  domain/
  integrations/
  models/
  repositories/
  schemas/
  services/
  tasks/
  workers/
```

Alvo incremental:

```text
backend/modules/
  access/
  catalog/
  fleet/
  orchestration/
  dispatch/
  telemetry/
  storage/
  governance/
```

Arquivos nao devem ser movidos em massa nesta etapa. Primeiro introduza portas
e adaptadores, depois mova modulo por modulo preservando imports legados.

## Arquivos a mover em etapas

- Access: `user`, `role`, auth e permissions.
- Catalog: automations, versions, manifests, packages, GitHub/import.
- Fleet: workers/agents, gateway registration, heartbeat, capabilities.
- Orchestration: jobs, executions, schedules, triggers.
- Dispatch: dispatcher, worker preferences, offers, reservations, leases.
- Telemetry: logs, realtime e event ingestion futuro.
- Storage: storage integrations, package resolver e uploads.
- Governance: audit, security policies e secrets futuros.

## Imports e adaptadores

- Manter import paths antigos ate cada modulo ter fachada publica.
- Criar adaptadores de leitura para telas legadas.
- Evitar import cruzado direto entre `modules/*/infrastructure`.
- Controllers devem chamar casos de uso de application.
- Handlers WebSocket devem traduzir protocolo e delegar regras.

## Estados antigos

- `pending` e `queued` continuam aceitos no frontend legado.
- `success` deve mapear para `succeeded` em modelos novos.
- `failed` permanece falha da tentativa ou tarefa, mas rejeicao de oferta usa
  `rejected` e nao deve falhar a automacao.
- `busy` nao deve mais ser armazenado como conectividade.

## Endpoints existentes

Manter temporariamente:

- `/api/v1/workers`
- `/api/v1/jobs`
- `/api/v1/executions`
- `/api/v1/agents:register`
- `/api/v1/agents/ws`

Adicionar endpoints novos em paralelo quando os modelos existirem:

- `/api/v1/agents`
- `/api/v1/agent-instances`
- `/api/v1/executions`
- `/api/v1/task-executions`
- `/api/v1/execution-attempts`
- `/api/v1/execution-offers`

## Protocolo antigo

`execution.assign` continua como compatibilidade. O protocolo novo usa:

```text
execution.offer -> execution.accepted/rejected -> execution.commit
```

Um adaptador pode traduzir `execution.assign` para oferta+commit somente para
Agents legados explicitamente marcados como `legacy_protocol=true`.

## Capabilities

Listas de strings continuam aceitas, mas devem ser normalizadas para objetos:

```json
{"key": "browser.playwright", "status": "available"}
```

## Frontend

Manter telas atuais com nomes legados enquanto novas APIs sao adicionadas.
Depois renomear UX de Workers para Agents e Jobs para Execucoes/Tarefas.

## Migrations necessarias

1. Criar tabelas `agents` e `agent_instances`.
2. Criar tabelas de capabilities e snapshots.
3. Criar `executions`, `task_executions`, `execution_attempts` novas ou
   evoluir as atuais com cuidado de nomes.
4. Criar `execution_offers`, `execution_leases`, `resource_locks` e
   `resource_reservations`.
5. Criar `agent_commands`, `inbox_messages`, `outbox_messages`.
6. Criar eventos estruturados com indice unico por tentativa e sequencia.
7. Migrar dados legados em lotes idempotentes.
