# Portal-Agent Protocol Matrix

Status: Prompt 1 final audit. Code and runtime smoke tests are the primary evidence.

| Message | Portal sends? | Portal receives? | Agent sends? | Agent receives? | Handler Portal | Handler Agent | Status | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent.connect` | NO | YES | YES | NO | `gateway/agent_gateway/endpoint.py` handshake | `PortalConnectionManager` | IMPLEMENTED | None for protocol 1.0 handshake. |
| `agent.connected` | YES | LEGACY | NO | YES | `endpoint.py` handshake response | `PortalConnectionManager` | IMPLEMENTED | Router still accepts legacy `agent.connected`/`agent.resumed`. |
| `agent.heartbeat` | NO | YES | YES | NO | `RecordAgentHeartbeat` via gateway router | `HeartbeatService` | IMPLEMENTED | Heartbeat is the main Fleet freshness source. |
| `portal.ack` | YES | NO | NO | YES | `endpoint.py` replies to routed messages | Portal ack handling services | IMPLEMENTED | Generic ACK envelope, correlated by message id. |
| `agent.command.ack` | NO | YES | YES | NO | `AcknowledgeAgentCommand` | `PortalInboxService` | IMPLEMENTED | ACK uses `command_id` and `command_sequence`. |
| `execution.offer` | YES | NO | NO | YES | `command_delivery.py` sends queued command | `ExecutionOfferHandler` | IMPLEMENTED | Payload now includes explicit execution, agent, automation, runtime, mode, resources, capabilities, TTL. |
| `execution.accepted` | NO | YES | YES | NO | `_handle_execution_accepted` -> accept + commit | `ExecutionOfferHandler` | IMPLEMENTED | Portal persists accept and creates `execution.commit`. |
| `execution.rejected` | NO | YES | YES | NO | `_handle_execution_rejected` -> reject + reschedule | `ExecutionOfferHandler` | IMPLEMENTED | Portal releases dispatch resources and avoids stuck execution. |
| `execution.commit` | YES | NO | NO | YES | `CommitExecutionOffer` queues command | `ExecutionCommitHandler` | IMPLEMENTED | Commit has explicit `execution_id`, attempt, offer, task, agent, lease. |
| `execution.cancel` | YES | NO | NO | YES | cancellation use case queues command | `ExecutionCancelRequestedHandler` | IMPLEMENTED | Official Portal -> Agent cancel command name. |
| `execution.cancel_requested` | LEGACY | NO | NO | LEGACY | Not supported as Agent -> Portal gateway message | compatibility naming in Agent docs/types | LEGACY | Keep as semantic state; use `execution.cancel` on the wire Portal -> Agent. |
| `execution.started` | NO | YES | YES | NO | `_handle_execution_started` | `ExecutionManager` via lifecycle publisher | IMPLEMENTED | Emitted after process launch, not by commit handler. |
| `execution.event.batch` | NO | YES | YES | NO | `_handle_execution_event_batch` -> Telemetry | `OutboxMessagePublisher` normalizes log/progress/metric/preparing | IMPLEMENTED | Ordering/dedup uses `execution_attempt_id + event_sequence`. |
| `execution.completed` | NO | YES | YES | NO | `_handle_execution_terminal` | `ExecutionManager` terminal outbox | IMPLEMENTED | Terminal success smoke passes. |
| `execution.failed` | NO | YES | YES | NO | same terminal router | `ExecutionManager` terminal outbox | IMPLEMENTED | Terminal failure smoke passes. |
| `execution.cancelled` | NO | YES | YES | NO | same terminal router | cancellation path / terminal outbox | IMPLEMENTED | Terminal cancel smoke passes. |
| `execution.timed_out` | NO | YES | YES | NO | same terminal router | terminal timeout outbox | IMPLEMENTED | Terminal timeout smoke passes. |
| `execution.lease.renew` | NO | YES | YES | NO | `_handle_execution_lease_renew` | `ExecutionLeaseManager` | IMPLEMENTED | Long-running lease-loss scenarios remain for later prompts. |
| `agent.sync_request` | YES | NO | NO | YES | queued command when application requests sync | `AgentSyncRequestHandler` | IMPLEMENTED | Portal-triggered sync is available as command path. |
| `agent.sync_state` | NO | YES | YES | NO | `ReconcileAgentSyncState` via gateway router | `AgentSyncService` | IMPLEMENTED | Basic in-sync/local-ahead/remote-ahead/conflict covered; restart recovery remains later. |
| `artifact.created` | NO | YES | YES | NO | `_handle_artifact_created` returns upload URL in `portal.ack` | `ArtifactManager` publishes | PARTIAL | Portal side tested; Agent durable upload lifecycle is Prompt 2. |
| `artifact.uploaded` | NO | YES | PARTIAL | NO | `_handle_artifact_uploaded` | upload manager path exists, mismatch remains | BLOCKED | `ARTIFACT_INTEGRATION = BLOCKED` until Prompt 2. |
| `artifact.failed` | NO | YES | PARTIAL | NO | `_handle_artifact_failed` | upload failure path exists, mismatch remains | BLOCKED | `ARTIFACT_INTEGRATION = BLOCKED` until Prompt 2. |

## Gateway Route Inventory

Incoming Agent -> Portal:

- IMPLEMENTED: `agent.heartbeat`, `agent.profile.updated`, `agent.capacity.updated`, `agent.capabilities.updated`, `agent.diagnostic.result`, `agent.sync_state`, `agent.update.progress`, `agent.command.ack`, `execution.accepted`, `execution.rejected`, `execution.lease.renew`, `execution.started`, `execution.event.batch`, `execution.completed`, `execution.failed`, `execution.cancelled`, `execution.timed_out`, `artifact.created`, `artifact.uploaded`, `artifact.failed`.
- LEGACY/compatibility: `agent.connected`, `agent.resumed` as routed messages; the primary connect path is the WebSocket handshake.
- DEFERRED: `execution.recovered`.

Outgoing Portal -> Agent:

- IMPLEMENTED: `agent.connected`, `portal.ack`, `portal.error`, `portal.disconnect`, `execution.offer`, `execution.commit`, `execution.cancel`, `agent.diagnostic.request`, `agent.capabilities.refresh`, `agent.update.request`, `agent.sync_request`.
- LEGACY naming to avoid: `execution.accept`, `execution.reject`, `execution.cancel_requested`, `command.ack`.

## Flow Notes

- Dispatch emits `execution.offer`; the delivery envelope supplies `message_id`, while command payload supplies `command_id` and `command_sequence`.
- `execution.accepted` commits the existing offer and queues `execution.commit`; it does not start execution locally in the Portal.
- `execution.rejected` persists the rejected offer, releases dispatch resources, and reschedules according to existing policy.
- `execution.started` is now a real host/process-start observation from the Agent, not a commit receipt.
- `agent.sync_state` records reconciliation rows and returns one of `IN_SYNC`, `LOCAL_AHEAD`, `REMOTE_AHEAD`, `CONFLICT`, `REQUIRES_INTERVENTION`.
- Artifacts are documented and smoke-tested on the Portal side, but the Agent upload lifecycle remains blocked for Prompt 2.
