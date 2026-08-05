# Agent Production Gap Review

Status: Bloco 6 final review, based on code inspection, real Portal smoke tests, and Agent automated tests.

## Executive Answer

The Automation Agent does not yet work completely end to end with the real Portal.

The base Portal-Agent wire contract was corrected for registration credentials, WebSocket handshake, heartbeat ACKs, offer decisions, command ACKs, event batches, leases, cancellation, and terminal messages. However, the complete path `Portal real -> Dispatch -> Agent real -> ExecutionHost real -> automation real -> result/artifacts -> Portal real` was not proven. The remaining blocker is not a single missing class; it is the absence of a certified real execution harness plus a concrete artifact protocol mismatch.

## Test Evidence

| Test | Result | Notes |
| --- | --- | --- |
| `dotnet build automation-agent\src\Agent.Service\Agent.Service.csproj` | PASS | Service and dependencies compiled successfully. |
| `dotnet test automation-agent\AutomationAgent.sln` | PASS | Agent unit/integration suite passed after code changes. |
| Host PowerShell Portal health/login/register/WS smoke | PASS | Real Portal accepted registration, WS handshake, heartbeat, and returned `portal.ack`. |
| `docker compose exec backend python gateway/agent_gateway/tests/smoke_gateway_flow.py` | PASS | Real Portal gateway smoke with synthetic WS client passed. |
| `docker compose exec backend python modules/orchestration/tests/smoke_execution_dispatch_flow.py` | FAIL | Failed before scenario: SQLAlchemy `NoReferencedTableError` for `automations.created_by_user_id -> users.id`. |
| `docker compose exec backend python modules/telemetry/tests/smoke_telemetry_completion_artifacts.py` | FAIL | Same SQLAlchemy metadata import failure before dispatch/telemetry scenario. |
| Agent.Service bounded real startup from Codex shell | INCONCLUSIVE | Could not observe a new Portal agent; background process control/inspection was limited by sandbox permissions. |

## BLOCKER

### Artifact upload lifecycle is not integrated with the real Portal

Expected: Agent sends `artifact.created`, Portal ACK returns `upload_url` and `upload_session_id`, Agent uploads bytes over HTTPS, then sends `artifact.uploaded` or `artifact.failed`.

Actual: Agent now wire-renames artifact creation to `artifact.created`, but `ArtifactUploadManager` still follows a separate REST-style initiate/confirm API path. The real Portal gateway returns upload instructions inside `portal.ack`, and the Agent does not consume that ACK result to upload the file.

Root cause: Artifact creation was treated as an outbox notification plus independent upload service, while the Portal contract is an ACK-driven upload session.

Impact: A real execution cannot complete the required result/artifact loop. Even if execution succeeds, artifacts will not reliably become downloadable in Portal storage.

Required fix: Persist artifact-created correlation, teach `PortalMessageAcknowledgementService` or a dedicated artifact ACK handler to capture upload URL/session, perform the PUT, and publish `artifact.uploaded`/`artifact.failed`. Add an integration test that uses the real Portal gateway contract.

### Full Portal-to-Agent background execution was not proven

Expected: A real Portal-created execution dispatches `execution.offer` to a real Agent.Service, Agent accepts, Portal sends `execution.commit`, Agent launches a real ExecutionHost/package, streams events, uploads artifact, and completes.

Actual: Registration and WS/heartbeat were proven against Portal real, but no certification automation reached a real Agent execution host from Portal in this run.

Root cause: The current dev setup lacks a deterministic harness that starts Agent.Service with a real registration token, preloads/imports a package/runtime the Agent can execute, creates the Portal automation version, and supervises shutdown. The Portal dispatch smoke scripts also currently fail before execution due backend test metadata import issues.

Impact: Production readiness cannot be claimed. Core protocols are aligned, but the actual operational loop remains unverified.

Required fix: Add a `certification.echo` package plus a reproducible e2e harness that seeds or downloads package/runtime through the intended flow, starts Agent.Service, creates execution via Portal API/UI, and asserts final Portal state, logs, progress, metrics, and artifact.

## HIGH

### Sync/reconciliation is not integrated with Portal gateway

Expected: On reconnect/restart, Agent publishes active executions, leases, inbox/outbox/artifacts, and Portal reconciles state.

Actual: Agent publishes `agent.sync_state` and has sync records locally, but the Portal gateway route table inspected for Bloco 6 does not route that message type.

Root cause: Agent implemented a sync protocol that is not yet backed by a Portal message handler.

Impact: Portal restart, Agent reconnect, and replay scenarios can drift. Active execution state may be lost or remain stale.

Required fix: Implement Portal `agent.sync_state` ingestion or align Agent to the Portal's actual reconciliation command/event if one exists. Add restart/reconnect tests.

### Backend dispatch/telemetry smoke scripts fail before execution

Expected: Smoke scripts should create a published automation version and exercise dispatch/telemetry/artifacts.

Actual: Both dispatch and telemetry smoke scripts fail with `NoReferencedTableError` because SQLAlchemy metadata for `users` is not loaded when creating an automation that references `created_by_user_id`.

Root cause: Test script imports do not include all ORM metadata needed by FK resolution.

Impact: The Portal has no runnable smoke evidence for dispatch/telemetry in the current container, reducing confidence and slowing certification.

Required fix: Import Access ORM models or central metadata initialization in the smoke scripts/test bootstrap, then rerun.

### Execution start event is approximate

Expected: `execution.started` should reflect the moment the ExecutionHost/process is actually launched.

Actual: `ExecutionCommitHandler` publishes `execution.started` before calling `ExecutionManager.ExecuteAsync`.

Root cause: Start event was added at command-handler boundary because existing ExecutionManager telemetry does not publish a start envelope itself.

Impact: Portal may show running before package/runtime validation or process launch actually succeeded.

Required fix: Move start publication into ExecutionManager after package/runtime are resolved and host launch succeeds, or add a separate `preparing` event and reserve `started` for real launch.

### Interactive restart/lock/session-runner flows are not proven

Expected: Interactive execution, locked session rejection, mid-run lock policy, exclusive control, and Session Runner crash recovery all work through Portal.

Actual: Local components exist, but no Portal-driven interactive scenario was executed.

Root cause: Base background E2E and artifact return are not complete; interactive also needs real Windows session controls and Session Runner process supervision.

Impact: Desktop automation cannot be certified for production.

Required fix: After background/browser baseline, run Notepad certification from Portal with locked-session and runner-crash scenarios.

## MEDIUM

### Fleet explicit profile/capacity/capability update path needs verification

Expected: Portal Fleet shows machine profile, capabilities, pools, slots, resource usage, running executions, version, online/offline, and last seen.

Actual: Heartbeat and direct WS smoke show pools/resources can reach Portal, but Agent explicit `agent.profile.updated`, `agent.capacity.updated`, and `agent.capabilities.updated` publication from Agent.Service was not proven.

Impact: Dispatch selection may make decisions from stale or incomplete Fleet data.

Required fix: Add explicit publish on startup/reconnect and Fleet API assertions.

### Browser automation remains behind background/artifact certification

Expected: Browser package launched from Portal via Agent, produces logs/screenshot/artifact, and cleans up.

Actual: Browser launcher exists but no Portal-driven browser run was executed.

Impact: Browser mode cannot be marked ready.

Required fix: Add safe local/static page certification after artifact lifecycle is fixed.

### Excel and Dominio are environment-dependent and untested

Expected: Excel certification preserves unrelated Excel processes; Dominio capability/lock validation is non-destructive and visible to Portal.

Actual: This run did not validate installed Excel or Dominio.

Impact: Production desktop targets remain uncertified for this machine.

Required fix: Run only on a prepared Windows desktop with those applications installed and a safe policy profile.

## LOW

### Real Agent.Service launch harness needs better process control

Expected: Codex/test harness starts Agent.Service, observes startup, captures logs, and shuts down cleanly.

Actual: Sandbox process APIs could not inspect command line or stop inherited `dotnet` children safely. Some observed `dotnet` processes may be build/compiler-server processes, but they could not be conclusively classified.

Impact: Local manual certification is awkward and can produce inconclusive results.

Required fix: Add a first-class test harness or CLI command that runs Agent.Service for a bounded duration and exits after registration/heartbeat.

## OPTIONAL

### Simulator fault injection should come after real baseline

Expected: Lost ACK, duplicate command, latency, invalid messages, reconnect, and out-of-order delivery are tested in Portal Simulator after real integration works.

Actual: Simulator is useful but not sufficient for Bloco 6 readiness.

Required fix: Keep simulator tests as secondary coverage once background real E2E is green.

## What Is Ready

- Portal real registration endpoint and credential issuance.
- Portal real WebSocket authentication, connect handshake, and heartbeat ACK.
- Agent protocol constants and outbound normalization for Portal's current message names.
- Agent local offer/accept/reject/commit/cancel/lease/idempotence tests.
- Agent build and automated unit/integration suite.

## What Is Partially Ready

- Fleet visibility through heartbeat snapshots.
- Dispatch offer and commit contracts.
- Logs/progress/metrics normalization into `execution.event.batch`.
- Lease renewal message shape.
- Cancel message intake and terminal cancellation.
- Restart/replay local mechanisms.

## What Exists Only As Local Or Protocol Work

- `agent.sync_state` exists in Agent but has no confirmed Portal gateway route.
- Browser/interactive/Excel/Dominio certification flows exist as local capability/launcher/session pieces, not proven through Portal real.
- Artifact pending/upload manager exists locally but does not implement the Portal ACK-driven upload contract.

## What Works In Mock But Not Proven Real

- Offer admission decisions.
- Duplicate offer/commit idempotence.
- Commit-to-ExecutionManager handoff.
- Cancel handler behavior.
- Lease renewal/loss.
- Event normalization from separate Agent events into Portal event batches.

## Objective Next Step

Make Bloco 6 certification executable and repeatable:

1. Fix the artifact ACK/upload lifecycle.
2. Fix backend smoke metadata imports.
3. Add `certification.echo`, `certification.fail`, and `certification.timeout`.
4. Add a bounded Agent.Service e2e runner with clean startup/shutdown and local package/runtime provisioning.
5. Run Portal-created executions through the real Agent and assert Portal API/UI data for logs, progress, metrics, result, artifacts, cancel, timeout, reconnect, and restart.
