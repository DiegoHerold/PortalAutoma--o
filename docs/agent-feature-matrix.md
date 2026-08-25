# Agent Feature Matrix

Status: Prompt 4 background execution certification update (2026-08-14). One
row corrected by Prompt 7 audit (2026-08-20) — see the "Replay/outbox after
reconnect" row below and `docs/certification/final-agent-feature-matrix.md`
for the superseding, full re-audit.

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
| Agent.Service real startup/status from certification harness | PASS: `.\scripts\certification.ps1 start` plus `status` observed Portal READY, Gateway READY, registered/online Agent, `Agent state: Ready`, runtime `python-core/3.13: READY`, PID file `47436`. |
| Portal -> Agent -> ExecutionHost background suite | PASS: `.\scripts\certification.ps1 run background`, run `cert_20260814_017`, OverallGate `PASS`; scenarios `echo`, `fail`, `timeout`, `cancel`, `progress`, and `artifact` all PortalE2E PASS. |

## Final Matrix

| Feature | Implemented | Integrated with Portal | Real-world tested | Automated test | Status | Gap | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agent registration | YES | YES | YES | YES | READY | Real Agent.Service registered/was found by name `certification-agent-01`, stayed online, and published heartbeat during Prompt 4 certification. | Keep startup/status in the certification harness. |
| Agent credential auth | YES | YES | YES | YES | READY | Portal expects `Bearer public_identifier:secret`; Agent now persists either `bearer_token` or reconstructed `public_identifier:secret`. Direct WS auth passed with real bearer token. | Keep credential round-trip covered with an Agent HTTP integration test. |
| WebSocket connect/handshake | YES | YES | YES | YES | READY | Agent now sends Portal-required `agent.connect` handshake and waits for `agent.connected`. Direct Portal WS smoke passed. | Add a real Agent.Service startup smoke outside sandbox process limits. |
| Protocol negotiation | YES | YES | YES | YES | READY | `supported_protocol_versions=["1.0"]` and selected protocol were validated against Portal gateway. | Keep supported-version fallback tests when adding protocol v2. |
| Heartbeat and ACK | YES | YES | YES | YES | READY | Agent now accepts `portal.ack` in addition to legacy heartbeat ACK. Direct heartbeat smoke passed. | Add backend assertion for `last_seen_at`/status transition in CI smoke. |
| Online/offline status | YES | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Agent.Service online/heartbeat was proven. A full stop/offline transition assertion was not part of the Prompt 4 background gate. | Add a bounded stop/offline assertion to the harness shutdown step. |
| Fleet profile | YES | PARTIAL | NO | YES | PARTIAL | Portal supports profile updates; Agent captures local profile. No explicit real `agent.profile.updated` flow observed from Agent.Service. | Wire or verify explicit profile publish after registration/reconnect. |
| Fleet capabilities | YES | PARTIAL | PARTIAL | YES | PARTIAL | Portal accepts `agent.capabilities.updated`; synthetic gateway smoke validates command path. Agent detects capabilities but not all execution capabilities are marked available (`agent.background_execution` is `NotConfigured`). | Publish real capability snapshot with Portal wire names and decide configured status for background/browser/interactive pools. |
| Fleet capacity | YES | PARTIAL | PARTIAL | YES | PARTIAL | Heartbeat can carry pool capacity and Portal stores pool data for real WS smoke. Explicit `agent.capacity.updated` from Agent not proven. | Add explicit capacity publish and Fleet assertions. |
| Dispatch selection | YES | YES | YES | PARTIAL | READY | Portal selected the real Agent for six Prompt 4 background executions and created committed offers with package/runtime requirements. | Add explicit multi-agent/fairness scenarios later. |
| `execution.offer` delivery | YES | YES | YES | YES | READY | Real Agent.Service received Portal offers, ran admission, reserved capacity, and accepted offers in run `cert_20260814_017`. | Keep duplicate/redelivery assertions in integration tests. |
| Offer accepted | YES | YES | YES | YES | READY | Agent emitted `execution.accepted`; Portal committed the offer and delivered `execution.commit` for the real background suite. | Add dedicated capability/capacity rejection E2E scenarios. |
| Offer rejected | YES | YES | PARTIAL | YES | PARTIAL | Agent now emits `execution.rejected` and normalizes rejection codes. Synthetic Portal code path supports it. | Run capability-mismatch and capacity-full scenarios through Portal. |
| Command ACK | YES | YES | YES | YES | READY | Real command delivery/retry was exercised by offer, commit, and cancel commands; duplicate redelivery was ignored after local terminal state. | Add explicit command ACK row checks to the JSON report. |
| `execution.commit` handling | YES | YES | YES | YES | READY | Real Portal commits launched one real `ExecutionHost.exe` per attempt in the Prompt 4 suite. | Keep single-launch duplicate commit regression. |
| Background execution success | YES | YES | YES | YES | READY | `certification.echo` succeeded via PortalE2E in run `cert_20260814_017`; events 1..21, ACK 21, artifact `result.txt` available. | Keep as the minimum smoke before broader suites. |
| Background failure | YES | YES | YES | YES | READY | `certification.fail` failed intentionally via PortalE2E in run `cert_20260814_017`; events 1..17, ACK 17, Portal status `failed`. | Keep expected-error extraction in the harness. |
| Background timeout | YES | YES | YES | YES | READY | `certification.timeout` timed out via PortalE2E in run `cert_20260814_017`; events 1..21, ACK 21, Portal status `timed_out`. | Add a longer lease-renewal timeout scenario later. |
| Portal cancel | YES | YES | YES | YES | READY | `certification.cancel` was cancelled through the real Portal cancel API; events 1..20, ACK 20, attempt/execution `cancelled`, cancellation request `completed`. | Shorten local graceful host shutdown if faster process teardown is desired. |
| Duplicate offer | YES | PARTIAL | NO | YES | PARTIAL | Agent offer handler is idempotent locally. Portal synthetic flow covers offer/reject paths, not real duplicate delivery to Agent. | Add simulator/fault injection after base real E2E passes. |
| Duplicate commit | YES | PARTIAL | NO | YES | PARTIAL | Commit repository blocks duplicate host launch in Agent tests. Real duplicate Portal command not exercised. | Add repeated `execution.commit` command test against Agent inbox. |
| Logs | YES | YES | YES | YES | READY | Real ExecutionHost stdout reached Portal telemetry as ordered `log` events in the Prompt 4 suite. | Add UI streaming validation separately. |
| Progress | YES | YES | YES | YES | READY | `certification.progress` succeeded with ordered progress events; run `cert_20260814_017` had events 1..23 and ACK 23. | Add UI real-time observation separately. |
| Metrics | YES | YES | YES | YES | READY | Host/process/runtime metrics and package metrics reached Portal; e.g. `certification.progress` stored 13 metric rows. | Add metric value assertions by name in the harness report. |
| Terminal success/failure/cancel/timeout | YES | YES | YES | YES | READY | Real terminal states were proven for `succeeded`, `failed`, `timed_out`, and `cancelled` in run `cert_20260814_017`. | Keep terminal duplicate/idempotence tests. |
| Artifacts | YES | YES | YES | YES | READY | Real artifact lifecycle passed: `artifact.created` ACK produced upload instructions, Agent uploaded bytes, sent `artifact.uploaded`, Portal confirmed `available`; `certification.artifact` stored three artifacts. | Keep checksum/object verification in certification evidence. |
| Leases | YES | YES | PARTIAL | YES | PARTIAL | Agent now releases the local lease on terminal attempts and emits `execution.lease.renew` with renewal sequence; real long execution lease renewal was not observed against Portal. | Run long-running certification and assert renewals/lease expiry behavior. |
| Replay/outbox after reconnect | YES | YES | NO | YES | HIGH | **Prompt 7 correction:** this row previously claimed the Portal gateway does not route `agent.sync_state`. That was false — `backend/gateway/agent_gateway/message_router.py:70,160-161` routes it to `_handle_agent_sync_state`/`ReconcileAgentSyncState`, and `backend/gateway/agent_gateway/tests/smoke_sync_state.py` passes (see `docs/portal-agent-integration-readiness.md`). The routing exists. The real, still-open gap is narrower: no scenario has ever run a live Portal disconnect *during an active execution*, then reconnect + outbox replay, end to end. | Build and run a certification scenario that starts a background execution, drops the Agent's WebSocket mid-run, lets it continue per policy, reconnects, and asserts Outbox replay reaches Portal with no loss/duplication. See `docs/certification/final-production-gap-review.md` H2. |
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
| 01 | Agent registration | PASS | Real Agent.Service online as `certification-agent-01`, heartbeat fresh, runtime ready. |
| 02 | Agent reconnect | BLOCKED | Needs controllable Agent.Service harness. |
| 03 | Heartbeat | PASS | Direct real Portal WS heartbeat returned `portal.ack` with `ok=true`. |
| 04 | Portal offline detection | PARTIAL | Direct WS client disconnect reflected offline later; Agent.Service offline cycle not proven. |
| 05 | Background execution success | PASS | `certification.echo`, run `cert_20260814_017`, execution `exe_339081b0ff014092878e5c141ed233ad`, Portal status `succeeded`. |
| 06 | Background failure | PASS | `certification.fail`, run `cert_20260814_017`, execution `exe_5068e00c88cb42e48ae9d2d5b1f8ecd2`, Portal status `failed`. |
| 07 | Background timeout | PASS | `certification.timeout`, run `cert_20260814_017`, execution `exe_d8fe4c2682ea423c8d12f7c1fcec3343`, Portal status `timed_out`. |
| 08 | Background cancel | PASS | `certification.cancel`, run `cert_20260814_017`, execution `exe_40539d3b97ef48c38a4fca28ae8753e8`, Portal status `cancelled`. |
| 09 | Browser execution | BLOCKED | Requires background baseline and artifact lifecycle fix. |
| 10 | Logs real-time | PASS | Real logs ingested into Portal telemetry with contiguous event ACKs; UI streaming not separately asserted. |
| 11 | Progress real-time | PASS | Real progress events ingested into Portal telemetry with contiguous event ACKs; UI streaming not separately asserted. |
| 12 | Metrics | PASS | Real metrics ingested into `execution_metrics` for all background scenarios. |
| 13 | Artifact | PASS | `certification.artifact`, run `cert_20260814_017`, stored `binary-test.bin`, `result.json`, and `small.txt` as `available`. |
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

Prompt 4 certifies the real background path end to end: Portal real -> Dispatch -> Agent Gateway -> Agent.Service real -> inbox/offer/admission/reservation -> commit -> ExecutionManager -> ExecutionHost.exe -> runtime/package -> telemetry/result/artifacts -> Portal. Browser, interactive, multi-agent, and active-restart/reconnect scenarios remain outside this background gate and must keep their separate status rows.
