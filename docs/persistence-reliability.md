# Persistencia e Confiabilidade

Status: vigente.

## Fonte de Verdade

PostgreSQL permanece a fonte oficial de verdade. A arquitetura nova reutiliza
`app.core.database`, `SessionLocal`, pool e Alembic existentes.

## Tabelas

A migration `9d8b0f2c4a11_catalog_persistence_reliability.py` adiciona:

- `automation_manifests`
- `automation_packages`
- `runtimes`
- `runtime_versions`
- `runtime_artifacts`
- `stored_objects`
- `upload_sessions`
- `outbox_messages`
- `inbox_messages`
- `agent_commands`
- `idempotency_records`
- `audit_events`

Tambem adiciona colunas nao destrutivas em:

- `automations`: `status`, `tags_json`, `created_by_user_id`
- `automation_versions`: `manifest_id`, `package_id`,
  `runtime_version_id`, campos de release/source e timestamps de bloqueio ou
  depreciacao

## Outbox

Eventos de Catalog sao gravados na mesma transacao das mudancas de estado. O
worker `backend/workers/outbox_worker.py` busca mensagens pendentes com
`FOR UPDATE SKIP LOCKED`, marca `processing`, publica internamente, marca
`published`, aplica retry/backoff e recupera mensagens presas.

## Inbox

`inbox_messages` registra `message_id` unico, hash de payload, status e
tentativas. A implementacao rejeita o mesmo ID com payload diferente. A
ingestao real de Agent fica para a etapa de Fleet/Gateway.

## AgentCommand

`agent_commands` persiste comandos, status e sequencia por `agent_instance_id`.
As chaves para Agent/AgentInstance ficam como strings sem FK nesta etapa,
porque Fleet ainda nao foi migrado. A entrega por WebSocket fica deferida.

## Idempotencia

`idempotency_records` usa `(scope, key)` unico e `request_hash`. Endpoints novos
de runtime, version e package upload, alem do `POST /automations` legado,
aceitam `Idempotency-Key`.

## Auditoria

`audit_events` e imutavel por convencao de repository e registra acoes de
Catalog, package e runtime. `audit_logs` legado permanece para a tela atual de
auditoria ate a migracao de Governance completa.
