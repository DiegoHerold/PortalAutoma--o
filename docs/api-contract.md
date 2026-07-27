# API Contract

Status: compatibilidade + direcao oficial.

Os endpoints abaixo existem ou representam a superficie atual do Portal. Os
contratos Portal-Agent versionados ficam em `contracts/` e o fluxo oficial em
`docs/protocol.md`.

## Endpoints atuais preservados

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/categories`
- `GET /api/v1/automations`
- `POST /api/v1/automations`
- `POST /api/v1/jobs`
- `GET /api/v1/workers`
- `GET /api/v1/health`
- `POST /api/v1/agents:register`
- `POST /api/v1/agents/{agent_id}/heartbeat`
- `POST /api/v1/agents/{agent_id}/events:batch`
- `WS /api/v1/agents/ws`

## Direcao oficial

Novas APIs devem expor a linguagem do dominio oficial:

- `Agent` e `AgentInstance`, nao apenas `Worker`.
- `Execution`, `TaskExecution`, `ExecutionAttempt` e `ExecutionOffer`, nao um
  unico `Job`.
- Eventos estruturados e versionados, nao apenas logs textuais.
- Downloads/uploads por Storage com URL temporaria, nao payload binario no
  WebSocket.

## Compatibilidade

`/jobs` e `/workers` continuam ativos ate a migracao descrita em
`docs/migration.md`. Novos consumidores devem preferir os contratos em
`contracts/protocol/v1/`.
