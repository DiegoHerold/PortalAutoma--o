# Final Agent Feature Matrix — Prompt 7 Audit

Status: Prompt 7 final audit. Superseding evidence for prior matrices is
`docs/agent-feature-matrix.md` (Prompt 4, 2026-08-14) and
`docs/portal-agent-protocol-matrix.md` / `docs/portal-agent-integration-readiness.md`
(Prompt 1, ~2026-08-12/13).

## Critical environment constraint

This audit ran in a session with **no working command execution against the
Portal/Agent machine** (`device_bash` returned `Workspace unavailable. The
isolated Linux environment on this device failed to start.` on every
attempt). No `dotnet build`, `dotnet test`, `docker compose`, live
`Agent.Service`, live Portal, or `.\scripts\certification.ps1` invocation was
possible. Every row below is graded from **static evidence** — code
inspection, prior report files, and git history — never from a fresh
execution. Per the prompt's own rule ("não confiar cegamente nos prompts
anteriores"), rows carry `(2026-08-14 evidence, not re-executed)` where the
only evidence is the prior Prompt 4 run.

## Repository baseline (see final-certification-report.md for full detail)

- Last git commit: `97343cd5` "PROMPT 2: Corrigir e certificar o lifecycle
  real de Artifacts Portal ↔ Automation Agent" (2026-08-06 in local time).
- `docs/certification-harness.md`, `docs/certification/background-certification-report.md`,
  and the current `agent-feature-matrix.md` are all **newer than the last
  commit** (file mtimes ≈ 2026-08-14) — i.e. all Prompt 3/4 work exists only
  as an uncommitted working tree, never captured in git history.
- No file anywhere in the repository (docs or source, outside build output)
  has a modification time after the Prompt 4 certification report. There is
  **no evidence Prompts 5 and 6** (recovery/reconnect/sync/restart
  certification; Browser/Interactive/Session Runner/Windows desktop
  certification) referenced in this prompt's own preamble ever executed
  against this repository — no new source files, no new docs, no commits.
  Treat any claim that they already happened as unverified.

## Documentation correction applied in this audit

`docs/agent-feature-matrix.md`'s row "Replay/outbox after reconnect" (HIGH)
states: *"Portal gateway does not route `agent.sync_state`."* This is
**false** against current code:

- `backend/gateway/agent_gateway/message_router.py:70` lists
  `"agent.sync_state"` in the routed incoming message set.
- `message_router.py:160-161` dispatches it to
  `_handle_agent_sync_state(...)` → `ReconcileAgentSyncState`.
- `backend/gateway/agent_gateway/tests/smoke_sync_state.py` (11.4 KB) exists
  and is the scenario `docs/portal-agent-integration-readiness.md` (Prompt 1)
  reports as PASS, matching `docs/portal-agent-protocol-matrix.md`'s
  `agent.sync_state: IMPLEMENTED` row.

The routing mechanism is real and implemented. The row is corrected below;
the genuine open gap is narrower than the old text (no live
disconnect-during-active-execution replay was ever exercised), not "route
missing."

## Final Matrix

| Feature | Implemented | Portal Integrated | Real Tested | Automated Test | Recovery Tested | Status | Evidence | Remaining Gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Agent registration | YES | YES | YES (2026-08-14, not re-executed) | YES | N/A | READY | `background-certification-report.md`: `certification-agent-01`, `agent_id=agt_CI0ZDEZtkhgWt1INDFEj7Bh`, online. | Re-run in a working live environment before shipping. |
| Credential auth | YES | YES | YES (2026-08-14) | YES | N/A | READY | Same run; bearer token accepted by Portal WS. | Re-run to confirm no regression. |
| WebSocket handshake | YES | YES | YES (2026-08-14) | YES | N/A | READY | `agent.connect → agent.connected` proven in Prompt 1 and Prompt 4 runs. | Re-run. |
| Heartbeat | YES | YES | YES (2026-08-14) | YES | N/A | READY | `portal.ack` with `ok=true` observed directly. | Re-run. |
| Online/offline transition | YES | PARTIAL | NO | PARTIAL | NO | PARTIAL | Heartbeat-online proven; a full stop→offline transition was never asserted in any run. | Add and execute a bounded stop/offline assertion (docs/agent-feature-matrix.md already flagged this in Prompt 4; still open). |
| Fleet profile/capabilities/capacity | YES | PARTIAL | PARTIAL | YES (unit only) | NO | PARTIAL | Heartbeat carries snapshot data; explicit `agent.profile.updated`/`agent.capacity.updated`/`agent.capabilities.updated` publish never observed live. | Unchanged since Prompt 4 — no new evidence found. |
| Dispatch / offer / accept / reject / commit | YES | YES | YES (2026-08-14) | YES | N/A | READY | Six real committed offers in `cert_20260814_017`. | Re-run; add explicit duplicate-offer/duplicate-commit live injection (still not done). |
| Command ACK | YES | YES | YES (2026-08-14) | YES | N/A | READY | Exercised by offer/commit/cancel commands in the same run. | Re-run. |
| Background success/failure/timeout/cancel | YES | YES | YES (2026-08-14) | YES | N/A | READY | `certification.echo/.fail/.timeout/.cancel`, all terminal states matched Portal exactly (see final-certification-report.md). | Re-run to confirm no regression since 2026-08-06 last commit. |
| Logs / Progress / Metrics / Result | YES | YES | YES (2026-08-14) | YES | N/A | READY | `certification.progress`: 23 ordered events, 13 metric rows. | UI streaming latency (Section 20) still not separately measured. |
| Artifacts | YES | YES | YES (2026-08-14) | YES | PARTIAL | READY | Full `artifact.created→ACK→PUT→artifact.uploaded→confirmed` proven with SHA-256 match on 3 files. | "Full live Agent process restart during in-flight large upload" explicitly listed as follow-up hardening in `artifact-integration-report.md`, never done. |
| Idempotency (dup offer/commit/cancel/ACK/telemetry) | YES (local) | PARTIAL | NO | YES (unit) | N/A | PARTIAL | Local idempotence covered by `Agent.UnitTests`/`Agent.IntegrationTests`; no real duplicate command was ever injected through the live Portal wire. | Add fault-injection test that sends a real duplicate `execution.commit` and observes `ExecutionHost` process count stays 1 (Section 29 of this prompt — never built). |
| Leases (renew / at-risk / lost) | YES | PARTIAL | PARTIAL | YES | NO | PARTIAL | Renewal message shape and terminal-release logic exist and are unit tested; no long-running live renewal cycle was ever observed against Portal. | Run a long-duration certification scenario spanning several heartbeat/lease cycles (Section 77) — never built. |
| `agent.sync_state` routing | YES | YES | YES (2026-08-12/13, Prompt 1) | YES | N/A | READY (corrected from prior HIGH) | `message_router.py:70,160-161`; `smoke_sync_state.py`; `portal-agent-integration-readiness.md` PASS row. | Route exists; see next row for the actual open gap. |
| Replay/outbox after disconnect **during an active execution** | PARTIAL | PARTIAL | NO | NO | NO | BLOCKED | Durable outbox and sync route both exist in isolation; the two were never exercised together against a live, in-flight execution. | Build and run: start a background execution, drop the WebSocket, let it continue, reconnect, assert outbox replay + no duplicate/lost telemetry. Genuinely never attempted per any file in this repo. |
| Portal restart during active execution | PARTIAL | NO | NO | NO | NO | BLOCKED | `agent-production-gap-review.md` and `portal-agent-integration-readiness.md` (Gaps #29) both state this was never run; nothing since contradicts that. | Same as above, from the Portal-restart side. |
| Agent restart during active execution | PARTIAL | PARTIAL | NO | PARTIAL | NO | BLOCKED | Agent has local orphan-execution recovery logic (unit tested); no Portal-backed live restart-with-active-execution was ever run. | Run controlled `Agent.Service` restart with a committed execution and observe lease/lock/outbox/inbox/process state. |
| Browser execution | YES (launcher) | PARTIAL | NO | PARTIAL | N/A | BLOCKED | Playwright/browser launcher code exists (root `.playwright-cli` tooling present); no Portal-dispatched browser execution has ever completed. | Run `certification`-style Playwright scenario against a safe local page, through Portal, end to end. Never attempted. |
| Interactive execution | YES (local) | PARTIAL | NO | PARTIAL | N/A | BLOCKED | `Agent.Application/Interactive/InteractiveExecutionCoordinator.cs`, `Agent.Application/Sessions/SessionRunnerPipeServer.cs`, `SessionRunnerRegistry.cs`, `InteractiveSessionSelector.cs` all exist and are locally unit tested. No Portal-driven interactive execution has ever completed. | Run the Notepad certification scenario through the real Portal with a real Session Runner. Never attempted per any doc or commit in this repo. |
| Session locked before offer | YES (local logic) | PARTIAL | NO | PARTIAL | N/A | BLOCKED | `DesktopLockManager.cs`/`DesktopLockKeys.cs` exist. | Never run against a real Portal-dispatched offer. |
| Session locked during execution | PARTIAL | PARTIAL | NO | PARTIAL | N/A | BLOCKED | Policy code exists; no live lock-mid-execution scenario run. | Same. |
| Second interactive execution (exclusivity) | YES (local pool logic) | PARTIAL | NO | YES (unit) | N/A | BLOCKED | `InteractivePoolService.cs` exists, locally tested. | Never dispatched two real interactive executions to the same session through Portal. |
| Session Runner crash/recovery | PARTIAL | PARTIAL | NO | PARTIAL | NO | BLOCKED | Runner registry/connection tracking exists; no real kill-and-recover test was run. | Kill a live `SessionRunner` process mid-execution, observe Agent detection and re-registration with new `instance_id`/`process_id`/`session_token`. |
| Excel | PARTIAL (detector only) | PARTIAL | NO | NO | N/A | NOT_APPLICABLE | `Agent.Windows/Detection/WindowsSoftwareDetector.cs` exists; no machine with Excel installed was available to this audit. | Needs certification on a target machine with Excel installed — explicitly an environment gap, not a code gap. |
| Dominio | PARTIAL (detector only) | PARTIAL | NO | NO | N/A | NOT_APPLICABLE | Same detector class covers generic software detection; no Dominio-specific evidence found. | Same as Excel — environment-dependent. |
| Capacity management / admission | YES | PARTIAL | PARTIAL | YES | N/A | PARTIAL | `Agent.Application/Capacity` exists and is unit tested; live admission-rejection scenarios (pool full, memory insufficient, draining, offline) were never run through Portal. | Run the six admission scenarios in Section 30 of this prompt live — never attempted. |
| Process ownership / PID reuse safety | YES | N/A | NO | PARTIAL | N/A | PARTIAL | `Agent.Windows/Process/WindowsApplicationProcessInspector.cs`, `WindowsSessionRunnerProcessValidator.cs`, `ProcessTreeManager.cs` exist and reason about more than raw PID. No dedicated PID-reuse adversarial test was found. | Add and run the PID-reuse regression test mandated in Section 43 — not found anywhere in `Agent.UnitTests`/`Agent.IntegrationTests`. |
| Security regression suite (Section 72 list) | NO | N/A | NO | NO | N/A | BLOCKED | No test file matching invalid-package-hash / path-traversal / invalid-pipe-token / expired-execution-token / oversized-message scenarios was located under `tests/`. Artifact path validation (rooted names, `..`, reparse points) and `RuntimeStore` SHA-256 verification exist as production code, which is partial, incidental coverage — not a dedicated adversarial suite. | Build the Section 72 adversarial test suite; none of it exists today. |
| Diagnostics export / secret scrubbing | PARTIAL | N/A | NO | PARTIAL | N/A | PARTIAL | `Certification.Core/Reporting/SecretScan.cs` exists as a last-resort regex guard for the certification report only, not a general Agent diagnostics export scrubber. | Confirm (by running) that the general diagnostics export path also scrubs bearer/session/execution tokens, not just the certification report. |
| Multiple Agents / fairness | PARTIAL | PARTIAL | PARTIAL | PARTIAL | N/A | PARTIAL | Portal can register multiple agents; two real isolated `Agent.Service` instances were never run simultaneously. | Unchanged since Prompt 4. |

## Summary counts

- READY: 11
- PARTIAL: 9
- BLOCKED: 9
- NOT_APPLICABLE: 2

None of the READY rows were independently re-executed in this Prompt 7
session; they carry forward 2026-08-06/08-12/08-14 evidence only, which is
the strongest evidence available in the repository, but is not a fresh
regression pass.
