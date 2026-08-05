# Portal-Agent Integration Readiness

Status: Prompt 1 completed. The integration infrastructure is operational and ready to start real execution certification. The Automation Agent is not declared 100% complete; artifact lifecycle remains Prompt 2.

`ARTIFACT_INTEGRATION = BLOCKED`

## Readiness Table

| Item | Implemented | Integrated | Tested | Status | Evidence | Gap |
| --- | --- | --- | --- | --- | --- | --- |
| Registration | YES | YES | YES | PASS | `smoke_gateway_flow.py`; real `/agents/register` with bearer credential. | None for Prompt 1. |
| WebSocket | YES | YES | YES | PASS | `agent.connect -> agent.connected` in `smoke_gateway_flow.py`. | None for protocol 1.0. |
| Heartbeat | YES | YES | YES | PASS | `agent.heartbeat -> portal.ack`; `last_seen_at` persisted. | Stale/offline timeout housekeeping not expanded here. |
| Fleet | YES | YES | YES | PASS | Heartbeat persists resources, pools, interactive session, health, version, connectivity. | Profile/capacity/capability messages exist; heartbeat remains the main freshness source. |
| Dispatch | YES | YES | YES | PASS | `smoke_execution_dispatch_flow.py`. | Full host launch certification belongs to later prompts. |
| Offer | YES | YES | YES | PASS | Smoke asserts command id, message id, execution id, attempt id, offer id, agent id, automation id/version, runtime, mode, resources, capabilities, TTL. | None for Prompt 1. |
| Accept | YES | YES | YES | PASS | `execution.accepted` persists offer accept and creates commit. | None for Prompt 1. |
| Reject | YES | YES | YES | PASS | `execution.rejected` persists rejection, releases/reconsiders dispatch, avoids stuck execution. | None for Prompt 1. |
| Commit | YES | YES | YES | PASS | `execution.commit` contains execution id, attempt id, offer id, task id, agent id, lease id/expires. | No separate reservation id is required by the current contract; lease is the commit grant. |
| Command ACK | YES | YES | YES | PASS | `agent.command.ack` by `command_id` and `command_sequence`. | `received_at` is represented by Portal acknowledgement time. |
| Telemetry | YES | YES | YES | PASS | `smoke_telemetry_completion_artifacts.py` log/progress/metric/event dedup/SSE. | None for Prompt 1. |
| Terminal events | YES | YES | YES | PASS | `completed`, duplicate terminal, `failed`, `cancelled`, `timed_out`. | None for Prompt 1. |
| Sync | YES | YES | YES | PASS | `smoke_sync_state.py` covers route/use case/reconciliation. | Restart recovery matrix remains later. |
| Artifacts | PARTIAL | PARTIAL | YES | BLOCKED | Portal returns upload URL, accepts upload, confirms `artifact.uploaded`, exposes download. | Agent durable upload lifecycle/mismatch is Prompt 2. |

## 1. Baseline Inicial

- `GET /api/v1/health`: PASS.
- `smoke_gateway_flow.py`: PASS.
- `smoke_execution_dispatch_flow.py`: FAIL before fix.
- `smoke_telemetry_completion_artifacts.py`: FAIL before fix.
- `dotnet test automation-agent/AutomationAgent.sln`: PASS, 168 unit + 101 integration.

## 2. Erros Encontrados

- `NoReferencedTableError` for `automations.created_by_user_id -> users.id` in dispatch and telemetry smoke bootstraps.
- `agent.sync_state` existed in Agent but had no Portal route/use case.
- `execution.started` could be emitted by `ExecutionCommitHandler` before a real process/host launch.
- `execution.offer`/`execution.commit` lacked explicit real `execution_id` in the Portal command payload.
- One transient PostgreSQL deadlock appeared during a telemetry rerun with live worker activity; it did not reproduce in the final clean run.

## 3. Causa Do NoReferencedTableError

The project uses one shared SQLAlchemy `Base`, but smoke scripts imported Catalog models without importing Access models. The FK target table `users` therefore was absent from `Base.metadata` at table creation time.

## 4. Correcao Metadata/Bootstrap

Created `backend/infrastructure/orm_metadata.py` with `initialize_orm_metadata()` and wired it into Alembic, API bootstrap, and smoke setup. It imports Access, Catalog, Fleet, Orchestration, Dispatch, Telemetry, Storage, Governance, and shared ORM modules.

## 5. Dispatch Smoke Antes/Depois

- Before: FAIL, ORM metadata incomplete.
- After: PASS, `execution dispatch smoke ok`.

## 6. Telemetry Smoke Antes/Depois

- Before: FAIL, ORM metadata incomplete.
- After: PASS, `telemetry completion artifacts smoke ok`.

## 7. Matriz Final Portal-Agent

See `docs/portal-agent-protocol-matrix.md`. `agent.sync_state` is now IMPLEMENTED. Artifact upload remains BLOCKED for Prompt 2.

## 8. Rotas Do Gateway

Incoming implemented: heartbeat, profile, capacity, capabilities, diagnostic result, update progress, command ack, accepted, rejected, lease renew, started, event batch, completed, failed, cancelled, timed out, sync state, artifact created/uploaded/failed.

Outgoing implemented: connected, ack, error, disconnect, offer, commit, cancel, diagnostic request, capabilities refresh, update request, sync request.

## 9. Contrato execution.offer

The Portal command envelope provides `message_id`; command delivery injects `command_id` and `command_sequence`. Payload now carries `execution_id`, `task_execution_id`, `execution_attempt_id`, `execution_offer_id`, `agent_id`, `agent_instance_id`, `automation_id`, `automation_version`, `runtime`, `execution_mode`, `resources`, `capabilities`, `required_pools`, locks, and TTL.

## 10. Contrato accepted/rejected

`execution.accepted` persists the offer acceptance and immediately queues `execution.commit`. `execution.rejected` persists rejection details, releases dispatch resources, and reschedules/reconsiders without marking the automation failed.

## 11. Contrato execution.commit

Commit now carries explicit execution/task/attempt/offer/agent identity plus `lease_id` and `lease_expires_at`. The current official contract does not require a separate `reservation_id`; the lease is the execution grant.

## 12. Command ACK

Portal ACK correlation is by `command_id` and `command_sequence`; status `received` maps to acknowledged command state.

## 13. Telemetry/event.batch

Event batch accepts log, progress, metric, and custom events. Ordering/deduplication uses `execution_attempt_id + event_sequence`, not timestamps.

## 14. Terminal Messages

`execution.completed`, `execution.failed`, `execution.cancelled`, and `execution.timed_out` close the attempt and update task/execution state. Duplicate terminal with same message is idempotent.

## 15. Correcao de execution.started

Removed the early `execution.started` publish from `ExecutionCommitHandler`. Added `IExecutionLifecyclePublisher` and `OutboxExecutionLifecyclePublisher`, called from `ExecutionManager` after `_processManager.LaunchAsync` returns and the process id is known.

## 16. Implementacao de agent.sync_state

Added `ReconcileAgentSyncState` in Dispatch application and routed `agent.sync_state` through the gateway. The gateway only routes; reconciliation rules live in the use case.

## 17. Estrategia de Reconciliation

Supported decisions: `IN_SYNC`, `LOCAL_AHEAD`, `REMOTE_AHEAD`, `CONFLICT`, `REQUIRES_INTERVENTION`. Local-ahead terminal states can apply Portal terminal handlers. Remote-ahead returns an explicit cancel action and does not kill inside sync. Conflicts are recorded without silent overwrite.

## 18. Fleet/profile/capacity/capabilities

Heartbeat is the official freshness path for last seen, connectivity, health, resource snapshot, pools, and interactive session. Separate profile/capacity/capability update messages remain implemented for targeted refreshes.

## 19. Testes Adicionados

- `gateway/agent_gateway/tests/smoke_sync_state.py`.
- Telemetry smoke now covers `cancelled` and `timed_out`.
- Dispatch smoke now asserts enriched offer/commit contract fields.
- Agent integration test asserts `execution.started` is not emitted by commit handler.

## 20. Testes Executados

- `Invoke-RestMethod http://localhost:8000/api/v1/health`.
- `Invoke-RestMethod http://localhost:8000/api/v1/agent-gateway/health`.
- `Invoke-RestMethod http://localhost:8000/api/v1/agent-gateway/readiness`.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_gateway_flow.py`.
- `docker compose exec backend python modules/orchestration/tests/smoke_execution_dispatch_flow.py`.
- `docker compose exec backend python modules/telemetry/tests/smoke_telemetry_completion_artifacts.py`.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_sync_state.py`.
- `dotnet test ./automation-agent/AutomationAgent.sln`.

## 21. Quantidade Total

- Agent .NET tests: 269 total, 269 passed.
- Portal smoke scripts: 4 end-to-end scripts passed, plus 3 health/readiness probes passed.

## 22. Cenarios PASS

Health, gateway readiness, registration, credential auth, WebSocket connect, protocol negotiation, heartbeat, heartbeat ack, online/disconnected transition, dispatch, offer, accept, reject, commit, command ACK, event batch, event dedup, terminal success/failure/cancel/timeout, sync route, sync in-sync, sync local-ahead, sync remote-ahead, sync conflict, Agent tests.

## 23. Cenarios FAIL

None in final run.

## 24. Cenarios BLOCKED

Artifacts full Agent lifecycle: BLOCKED for Prompt 2. Portal-side artifact URL/upload/download contract is tested.

## 25. Arquivos Criados

- `backend/infrastructure/orm_metadata.py`.
- `backend/modules/dispatch/application/use_cases/reconciliation.py`.
- `backend/gateway/agent_gateway/tests/smoke_sync_state.py`.
- `automation-agent/src/Agent.Application/Execution/IExecutionLifecyclePublisher.cs`.
- `automation-agent/src/Agent.Application/Messaging/OutboxExecutionLifecyclePublisher.cs`.
- `docs/portal-agent-integration-readiness.md`.

## 26. Arquivos Alterados

Key files: API/Alembic bootstrap, gateway endpoint/router/connection manager, Dispatch scheduler/offers/DTO exports, orchestration and telemetry smokes, Agent offer/commit payloads and handlers, `ExecutionManager`, Agent DI registration, Agent commit test, protocol matrix docs.

## 27. Migrations

No new migration was required. Existing reconciliation tables and dispatch/telemetry tables were reused.

## 28. Documentacao Atualizada

- `docs/portal-agent-protocol-matrix.md`.
- `docs/portal-agent-integration-readiness.md`.

## 29. Gaps Restantes

- `ARTIFACT_INTEGRATION = BLOCKED` for Prompt 2.
- Restart/reconnect recovery beyond the four basic sync decisions is not complete.
- Long-running lease-loss/fault injection scenarios remain later.
- Stale/offline timeout detector is present but not expanded in Prompt 1 smoke beyond immediate `disconnected`.
- Real ExecutionHost launched by Portal is still outside Prompt 1.

## 30. Pronto Para Prompt 2

YES. The Portal can dispatch, process Agent responses, receive telemetry, close executions, and reconcile state. The next step is Prompt 2: fix the complete artifact lifecycle according to the real Portal protocol.
