# Agent Feature Matrix

Status: final Bloco 6 Portal-Agent integration review.

Primary evidence is implementation code, migrations/runtime behavior, and tests. Documentation remains secondary and any capability not backed by code or execution evidence is marked as `DOCUMENTED_ONLY`, `PARTIAL`, or `BLOCKED`.

## Evidence Collected

| Evidence | Result |
| --- | --- |
| Portal real health check | PASS: `GET /api/v1/health` returned `status=ok`. |
| Portal real agent registration API | PASS: `POST /api/v1/agents/register` accepted real request shape and returned `agent.id` plus `credential.bearer_token`. |
| Portal real WebSocket gateway | PASS: host PowerShell `ClientWebSocket` connected to `ws://localhost:8000/api/v1/agent-gateway/connect`, sent `agent.connect`, received `agent.connected`, sent `agent.heartbeat`, received `portal.ack` with `ok=true`. |
| Portal gateway smoke script | PASS: `docker compose exec backend python gateway/agent_gateway/tests/smoke_gateway_flow.py`. |
| Portal dispatch/telemetry smoke scripts | FAIL before scenario execution: SQLAlchemy metadata import gap (`automations.created_by_user_id` could not resolve table `users`). |
| Agent automated tests | PASS: `dotnet test automation-agent\AutomationAgent.sln` passed before and after integration changes. |
| Agent.Service real long-running startup from Codex shell | INCONCLUSIVE: process launch control could not produce a new observed Portal agent within the bounded window; Codex sandbox also could not safely inspect/stop all `dotnet` children by command line. Not counted as product PASS. |

## Final Matrix

| Feature | Implemented | Integrated with Portal | Real-world tested | Automated test | Status | Gap | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agent registration | YES | YES | PARTIAL | YES | PARTIAL | Agent HTTP contract now maps Portal's real `local_identity`, `machine_fingerprint`, OS string, and `credential.bearer_token`; direct Portal registration passed. Agent.Service self-registration was not conclusively observed from the constrained launch test. | Add a bounded Agent.Service e2e harness that starts the worker, waits for registered identity, then shuts down cleanly. |
| Agent credential auth | YES | YES | YES | YES | READY | Portal expects `Bearer public_identifier:secret`; Agent now persists either `bearer_token` or reconstructed `public_identifier:secret`. Direct WS auth passed with real bearer token. | Keep credential round-trip covered with an Agent HTTP integration test. |
| WebSocket connect/handshake | YES | YES | YES | YES | READY | Agent now sends Portal-required `agent.connect` handshake and waits for `agent.connected`. Direct Portal WS smoke passed. | Add a real Agent.Service startup smoke outside sandbox process limits. |
| Protocol negotiation | YES | YES | YES | YES | READY | `supported_protocol_versions=["1.0"]` and selected protocol were validated against Portal gateway. | Keep supported-version fallback tests when adding protocol v2. |
| Heartbeat and ACK | YES | YES | YES | YES | READY | Agent now accepts `portal.ack` in addition to legacy heartbeat ACK. Direct heartbeat smoke passed. | Add backend assertion for `last_seen_at`/status transition in CI smoke. |
| Online/offline status | YES | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Portal updates `last_seen_at` and disconnect state for direct WS clients. Full Agent.Service online/offline cycle not proven in this run. | Run Agent.Service under a controllable supervisor and assert Fleet `connectivity_status` transitions. |
| Fleet profile | YES | PARTIAL | NO | YES | PARTIAL | Portal supports profile updates; Agent captures local profile. No explicit real `agent.profile.updated` flow observed from Agent.Service. | Wire or verify explicit profile publish after registration/reconnect. |
| Fleet capabilities | YES | PARTIAL | PARTIAL | YES | PARTIAL | Portal accepts `agent.capabilities.updated`; synthetic gateway smoke validates command path. Agent detects capabilities but not all execution capabilities are marked available (`agent.background_execution` is `NotConfigured`). | Publish real capability snapshot with Portal wire names and decide configured status for background/browser/interactive pools. |
| Fleet capacity | YES | PARTIAL | PARTIAL | YES | PARTIAL | Heartbeat can carry pool capacity and Portal stores pool data for real WS smoke. Explicit `agent.capacity.updated` from Agent not proven. | Add explicit capacity publish and Fleet assertions. |
| Dispatch selection | YES | PARTIAL | NO | PARTIAL | PARTIAL | Portal dispatch exists, but dispatch smoke script currently fails before flow because test imports omit Access `users` metadata. Real Agent-dispatched execution not proven. | Fix backend smoke metadata import and run dispatch flow with real Agent, not synthetic client. |
| `execution.offer` delivery | YES | YES | PARTIAL | YES | PARTIAL | Portal command delivery and Agent handler align on `execution.offer`; synthetic Portal smoke covers delivery. Real Agent.Service receipt from Portal not proven. | Run certification execution through Portal to Agent.Service. |
| Offer accepted | YES | YES | PARTIAL | YES | PARTIAL | Agent now emits `execution.accepted` with `execution_offer_id`, `execution_attempt_id`, `agent_id`, `agent_instance_id`, `accepted_at`, reservations. Synthetic Portal code path supports it. | Validate with real Portal-dispatched offer and Agent outbox. |
| Offer rejected | YES | YES | PARTIAL | YES | PARTIAL | Agent now emits `execution.rejected` and normalizes rejection codes. Synthetic Portal code path supports it. | Run capability-mismatch and capacity-full scenarios through Portal. |
| Command ACK | YES | YES | PARTIAL | YES | PARTIAL | Agent now emits `agent.command.ack` with command id/sequence and handles Portal `portal.ack`. | Validate command ACK persistence from real Agent inbox/outbox. |
| `execution.commit` handling | YES | YES | PARTIAL | YES | PARTIAL | Agent handles `execution.commit`; now resolves missing top-level execution id via latest accepted offer. | Prove commit delivery from Portal real into Agent.Service and single ExecutionHost launch. |
| Background execution success | YES | PARTIAL | NO | YES | BLOCKED | Agent can run local packages, but no real Portal-created execution reached a real Agent execution host in this run. Local package/runtime pre-seeding and Agent.Service launch harness are missing. | Build certification package seeding/download path and run `certification.echo` from Portal. |
| Background failure | YES | PARTIAL | NO | YES | BLOCKED | Local failure handling exists, but real Portal-originated failure was not executed. | Add `certification.fail` and assert Portal final state/log/error. |
| Background timeout | YES | PARTIAL | NO | YES | BLOCKED | Timeout/cancel machinery exists locally, but Portal-to-Agent timeout path was not executed. | Add long-running certification automation with Portal timeout policy. |
| Portal cancel | YES | YES | NO | YES | PARTIAL | Agent now handles Portal `execution.cancel`; cancelling is normalized through event batch and terminal `execution.cancelled` is supported. Real Portal cancel button/API was not exercised against Agent.Service. | Run long execution, send Portal cancel, assert one final state. |
| Duplicate offer | YES | PARTIAL | NO | YES | PARTIAL | Agent offer handler is idempotent locally. Portal synthetic flow covers offer/reject paths, not real duplicate delivery to Agent. | Add simulator/fault injection after base real E2E passes. |
| Duplicate commit | YES | PARTIAL | NO | YES | PARTIAL | Commit repository blocks duplicate host launch in Agent tests. Real duplicate Portal command not exercised. | Add repeated `execution.commit` command test against Agent inbox. |
| Logs | YES | YES | PARTIAL | YES | PARTIAL | Agent now normalizes `execution.log` to Portal `execution.event.batch`. Portal telemetry smoke for logs is blocked by backend test import error; real Agent logs not observed in Portal UI. | Fix backend smoke and run certification logs with progressive Portal/UI observation. |
| Progress | YES | YES | PARTIAL | YES | PARTIAL | Agent normalizes progress to event batch. No real Portal UI progression observed. | Run 0/20/40/60/80/100 certification and assert event sequences. |
| Metrics | YES | YES | PARTIAL | YES | PARTIAL | Agent normalizes metrics to event batch and terminal resource usage. No real Portal UI/API metrics observed from Agent.Service. | Assert `/executions/{id}/metrics` after real Agent execution. |
| Terminal success/failure/cancel/timeout | YES | YES | PARTIAL | YES | PARTIAL | Message names align; Agent enriches terminal payloads with attempt, agent, timestamp, event sequence defaults. Not proven with real ExecutionHost from Portal. | Run success, fail, timeout, cancel certification cases. |
| Artifacts | PARTIAL | NO | PARTIAL | YES | BLOCKER | Portal real lifecycle is `artifact.created` -> `portal.ack` with upload URL -> HTTPS PUT -> `artifact.uploaded`. Agent still has a REST-style `ArtifactUploadManager` initiate/confirm path and does not consume upload URL from `artifact.created` ACK. | Rework Agent artifact upload to capture `portal.ack` result, PUT bytes to upload URL, then send `artifact.uploaded`/`artifact.failed`. |
| Leases | YES | YES | NO | YES | PARTIAL | Agent now emits `execution.lease.renew` with renewal sequence; real long execution lease renewal was not observed against Portal. | Run long-running certification and assert renewals/lease expiry behavior. |
| Replay/outbox after reconnect | YES | PARTIAL | NO | YES | HIGH | Durable outbox exists and Agent sends sync on reconnect, but Portal gateway does not route `agent.sync_state`. | Add Portal route/use case for `agent.sync_state` or adapt Agent to Portal's implemented reconciliation command. |
| Portal restart during execution | PARTIAL | NO | NO | PARTIAL | HIGH | Agent local recovery exists; Portal sync endpoint is missing, and no real active execution restart test was run. | Implement/align reconciliation, then run Portal restart scenario. |
| Agent restart during execution | PARTIAL | PARTIAL | NO | YES | HIGH | Agent can recover orphaned local executions and leases, but no real Portal-backed active execution restart was run. | Run controlled service restart with committed execution, locks, lease, outbox, and process observation. |
| Browser execution | YES | PARTIAL | NO | PARTIAL | BLOCKED | Browser launcher exists. Portal-to-Agent background baseline is not proven, and screenshot/artifact return is blocked by artifact lifecycle. | After background success, run Playwright certification against safe local/static page. |
| Interactive execution | YES | PARTIAL | NO | PARTIAL | BLOCKED | Session Runner, selectors, locks, and interactive coordinator exist locally. Portal real command path and Session Runner participation were not executed. | After background/browser pass, run Notepad certification from Portal with real Session Runner. |
| Session locked before offer | YES | PARTIAL | NO | PARTIAL | BLOCKED | Agent can reason about session status locally; Portal real rejection path for locked session not tested. | Run locked-session offer and assert `INTERACTIVE_SESSION_LOCKED` or equivalent rejection. |
| Session locked during execution | PARTIAL | PARTIAL | NO | PARTIAL | BLOCKED | Policy exists, but real lock event during Portal execution was not run. | Run Notepad flow and lock/unlock scenario. |
| Second interactive execution | YES | PARTIAL | NO | YES | BLOCKED | Local exclusive pool/lock logic exists; real Portal concurrent interactive dispatch not tested. | Dispatch two interactive executions to same Agent/session. |
| Session Runner crash | PARTIAL | PARTIAL | NO | PARTIAL | BLOCKED | Runner connection tracking exists; crash/reconnect not proven through Portal. | Kill SessionRunner during real execution and assert coherent state. |
| Excel | PARTIAL | PARTIAL | NO | NO | NOT_APPLICABLE | Excel installation/environment was not verified in this run. | Test only on machine with Excel installed, preserving unrelated manual Excel process. |
| Dominio capability/lock | PARTIAL | PARTIAL | NO | NO | NOT_APPLICABLE | Dominio installation/environment was not verified; detector exists. | Test safe capability/lock only on machine with Dominio installed. |
| Multiple Agents | YES | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Portal can register multiple agents; synthetic smoke covers two clients. Two real isolated Agent.Service instances were not proven. | Add deterministic two-instance dev harness with distinct data dirs and credentials. |

## Mandatory Real Scenario Matrix

| # | Scenario | Status | Evidence |
| --- | --- | --- | --- |
| 01 | Agent registration | PARTIAL | Direct Portal API PASS; Agent.Service self-registration not conclusively observed. |
| 02 | Agent reconnect | BLOCKED | Needs controllable Agent.Service harness. |
| 03 | Heartbeat | PASS | Direct real Portal WS heartbeat returned `portal.ack` with `ok=true`. |
| 04 | Portal offline detection | PARTIAL | Direct WS client disconnect reflected offline later; Agent.Service offline cycle not proven. |
| 05 | Background execution success | BLOCKED | No real Portal -> Agent.Service -> ExecutionHost flow. |
| 06 | Background failure | BLOCKED | Requires real background execution baseline. |
| 07 | Background timeout | BLOCKED | Requires real background execution baseline. |
| 08 | Background cancel | BLOCKED | Requires real background execution baseline and Portal cancel command. |
| 09 | Browser execution | BLOCKED | Requires background baseline and artifact lifecycle fix. |
| 10 | Logs real-time | BLOCKED | Event normalization implemented; no real Portal/UI streaming from Agent.Service. |
| 11 | Progress real-time | BLOCKED | Event normalization implemented; no real Portal/UI streaming from Agent.Service. |
| 12 | Metrics | BLOCKED | Event normalization implemented; no real Portal metrics from Agent.Service. |
| 13 | Artifact | FAIL | Agent artifact upload lifecycle does not match Portal upload URL ACK flow. |
| 14 | Duplicate offer | PARTIAL | Agent idempotence covered locally; no real duplicate command injection. |
| 15 | Duplicate commit | PARTIAL | Agent idempotence covered locally; no real duplicate command injection. |
| 16 | Portal disconnect during execution | BLOCKED | Requires real active execution. |
| 17 | Portal reconnect | BLOCKED | Requires real active execution and sync support. |
| 18 | Agent restart | BLOCKED | Requires real active execution. |
| 19 | Interactive execution | BLOCKED | Requires background baseline, Session Runner, and Portal flow. |
| 20 | Session locked before offer | BLOCKED | Requires interactive Portal flow. |
| 21 | Session locked during execution | BLOCKED | Requires interactive Portal flow. |
| 22 | Session Runner crash | BLOCKED | Requires interactive Portal flow. |
| 23 | Second interactive execution | BLOCKED | Requires interactive Portal flow. |
| 24 | Excel | NOT_APPLICABLE | Excel environment not validated in this run. |
| 25 | Dominio capability/lock | NOT_APPLICABLE | Dominio environment not validated in this run. |

## Final Conclusion

The Automation Agent is substantially closer to Portal compatibility after Bloco 6 protocol alignment, but it is not production-ready end to end. The proven real path today is Portal registration API plus WebSocket authentication/handshake/heartbeat. The unproven and blocking path is the full user-triggered Portal execution reaching a real Agent.Service, launching a real ExecutionHost, returning logs/progress/metrics/result/artifacts, and surviving cancel/restart/reconnect scenarios.
