# Final Production Gap Review — Prompt 7 Audit

Date: 2026-08-20. Method: static code/doc audit only (see
final-certification-report.md for why no live execution was possible this
session). Each item follows Problem / Expected / Actual / Evidence / Root
cause / Impact / Required fix / Owner-component.

## BLOCKER

### B1 — This audit could not execute anything live

- Problem: Prompt 7 requires re-running the build, the automated test
  suites, and `.\scripts\certification.ps1`, and comparing against prior
  results to catch regressions.
- Expected: `dotnet build`/`dotnet test`, `docker compose`, and
  `certification.ps1 run background` (at minimum) execute and produce fresh
  PASS/FAIL evidence.
- Actual: every `device_bash` call this session returned `Workspace
  unavailable. The isolated Linux environment on this device failed to
  start.` No command ran on the Portal/Agent machine at any point.
- Evidence: tool error captured verbatim at the start of this audit.
- Root cause: the desktop bridge's local command-execution workspace failed
  to boot for this session; file listing/staging/commit tools remained
  available, command execution did not.
- Impact: no scenario in this report — including the ones marked READY from
  prior evidence — was independently re-verified. The release gate cannot
  mathematically reach APPROVED while this holds, independent of product
  quality.
- Required fix: re-run this audit (or just the automated regression step)
  in a session/machine where `device_bash` (or direct developer access) is
  functional. This is an environment/tooling blocker, not a product defect.
- Owner/component: session infrastructure, not Portal or Agent code.

### B2 — Interactive, Browser, and full recovery paths have never completed once against a real Portal

- Problem: three of the twenty-one scenarios this prompt defines as "Core"
  (Section 90) — Browser execution, Interactive execution, Session
  exclusivity — plus two more (Portal reconnect, Agent reconnect) have zero
  recorded successful end-to-end runs anywhere in this repository's history.
- Expected: per Section 92 (Definition of Done), the path Portal → Agent →
  ExecutionHost → Automation → Portal must be proven for "principais modos"
  including these.
- Actual: `docs/agent-feature-matrix.md`'s own Prompt 4 matrix marks all
  five as `BLOCKED`; nothing in the repository (no new commit, no new doc,
  no source file with a later mtime) shows this changed since 2026-08-14.
- Evidence: `docs/agent-feature-matrix.md` rows 54-59; `.git/logs/HEAD`
  shows no commit after `97343cd5` (PROMPT 2, ≈2026-08-06); no source file
  under `automation-agent/src/Agent.Application/Interactive`,
  `.../Sessions`, or any browser-launcher path has a modification time
  after the Prompt 4 certification report.
- Root cause: Prompts 5 and 6, which this prompt's own preamble assumes
  already certified these paths, left no trace in this repository. Either
  they were never run, or they ran somewhere this repository does not
  reflect.
- Impact: the core claim "Automation Agent está pronto para operar
  integrado ao Portal" cannot be supported for interactive or browser
  automation, or for any recovery scenario involving an active execution.
  These are exactly the capabilities most likely to touch real client
  desktops (Excel, Domínio, RDP-driven work) once Fase 3 ships.
- Required fix: build and run, on a real Windows machine with the harness
  from `docs/certification-harness.md`, at minimum: one Notepad interactive
  scenario, one Playwright/local-page browser scenario, and one
  Agent-restart-during-active-execution scenario. None of the scaffolding
  is missing — the classes exist — only the live proof is missing.
- Owner/component: `Agent.Application/Interactive`, `Agent.Application/Sessions`,
  browser launcher, `Agent.Service` restart path, `Certification.Cli`.

## HIGH

### H1 — Documentation falsely claims `agent.sync_state` is unrouted (corrected in this audit)

- Problem: `docs/agent-feature-matrix.md` row "Replay/outbox after
  reconnect" states the Portal gateway does not route `agent.sync_state`,
  and grades the row HIGH on that basis.
- Expected: documentation should match the code that is the primary
  evidence source (Section 3 of this prompt).
- Actual: `backend/gateway/agent_gateway/message_router.py:70` includes
  `"agent.sync_state"` in the routed set, and lines 160-161 dispatch it to
  `_handle_agent_sync_state` → `ReconcileAgentSyncState`.
  `backend/gateway/agent_gateway/tests/smoke_sync_state.py` exists (11.4 KB)
  and `docs/portal-agent-integration-readiness.md` records it PASS.
- Evidence: file contents quoted above; corrected row in
  `final-agent-feature-matrix.md`.
- Root cause: `docs/agent-feature-matrix.md` (Prompt 4) was written without
  re-checking a fix that had already landed in Prompt 1 (2026-08-12/13,
  before Prompt 4's 2026-08-14 pass) — a direct instance of the failure
  mode this Prompt 7 warns about ("documentação diz que funciona" cuts both
  ways: it also wrongly says something does *not* work).
- Impact: previously overstated severity; the real remaining gap (see B2
  and H2) is narrower than "the route is missing."
- Required fix: applied in this audit — `docs/agent-feature-matrix.md`'s row
  should be edited to remove the false claim (tracked in
  final-certification-report.md "Fixes Applied").
- Owner/component: documentation only; no code change required.

### H2 — Replay/reconciliation was never exercised against a live, in-flight execution

- Problem: the outbox/sync mechanism and the routing exist independently,
  but disconnect → continue running → reconnect → replay was never run as
  one scenario.
- Expected: Section 35-37 of this prompt — Portal disconnects mid-execution,
  automation continues per policy, events queue in Outbox, reconnect
  triggers sync + replay, Portal recovers events with no loss/duplication.
- Actual: no report, test, or doc in this repository describes this
  scenario running, live or otherwise.
- Evidence: absent from `docs/agent-feature-matrix.md` (`Portal disconnect
  during execution` = BLOCKED, `Portal reconnect` = BLOCKED in the
  Mandatory Real Scenario Matrix), absent from
  `docs/certification/background-certification-report.md`'s explicit
  "Remaining Scope" list ("Agent/Portal restart during active execution").
- Root cause: every certified scenario so far (echo/fail/timeout/cancel/
  progress/artifact) runs start-to-finish without any Portal disconnect
  injected.
- Impact: the single most operationally important recovery path (a Portal
  restart or network blip while automations are running client work) is
  unverified. HIGH because a coherence failure here directly risks
  duplicate execution or silent data loss (Section 6, "HIGH" criteria).
- Required fix: extend `Certification.Cli`/the certification packages with
  a long-running scenario, disconnect the Agent's WebSocket mid-run
  (`PortalConnectionManager`), let it finish locally, reconnect, and assert
  Outbox replay reaches Portal with correct sequence and no duplicates.
- Owner/component: `Agent.Application/Connection/PortalConnectionManager.cs`,
  `Agent.Application/Sync`, Dispatch reconciliation use case, certification
  harness.

### H3 — No automated security regression suite exists

- Problem: Section 72 of this prompt lists eight adversarial scenarios
  (invalid package hash, invalid manifest, path traversal, invalid pipe
  token, expired execution token, unauthorized Session Runner, oversized
  protocol message, invalid Agent credential) as mandatory before release.
- Expected: at least one automated test per scenario.
- Actual: no test file matching any of these names or intents was found
  under `automation-agent/tests/Agent.UnitTests`,
  `Agent.IntegrationTests`, or `backend/gateway/agent_gateway/tests`.
  Related production code exists incidentally — artifact path validation
  rejects rooted paths/`..`/reparse points
  (`docs/artifact-integration-report.md` §8), and `RuntimeStore` verifies
  SHA-256 on import (`docs/certification-harness.md` §8) — but neither is
  exercised by a hostile-input test.
- Evidence: directory listings of both test projects (see
  final-certification-report.md); grep of file names for
  `path.?traversal|pid.?reuse|pipe.?token|oversized|expired.?token` returned
  nothing.
- Root cause: security hardening so far has been a byproduct of correctness
  work (e.g. artifact path validation), never a deliberate adversarial pass.
- Impact: unknown blast radius — this audit cannot certify that a
  compromised or buggy package/manifest/pipe client is safely rejected.
- Required fix: write and run the Section 72 suite.
- Owner/component: `Agent.Infrastructure/Stores` (package/runtime),
  `Agent.Application/Sessions` (pipe token), `Agent.Service` (credential),
  new test project or additions to `Agent.IntegrationTests`.

### H4 — PID-reuse and long-running-lease regressions have no automated coverage

- Problem: Sections 43 (PID reuse) and 77 (long-running test spanning
  several heartbeat/lease cycles) are both explicitly required.
- Expected: a test proving a reused PID does not make the Agent adopt an
  unrelated process, and at least one certification run exceeding several
  heartbeat/lease renewal cycles.
- Actual: `Agent.Windows/Process/WindowsApplicationProcessInspector.cs` and
  `WindowsSessionRunnerProcessValidator.cs` reason about more than PID
  (start time, session, path per `docs/certification-harness.md` intent),
  but no test file exercises a simulated PID-reuse collision. All six
  certification packages (echo/fail/timeout/cancel/progress/artifact) are
  short-lived; none was run long enough to force multiple lease renewals.
- Evidence: directory listings of `Agent.UnitTests`/`Agent.IntegrationTests`
  `Sessions`/`Execution` subfolders; `background-certification-report.md`
  scenario table shows all six runs completing in well under one lease
  period.
- Root cause: certification packages were designed to prove the pipeline,
  not lifecycle edge cases.
- Impact: PID-reuse and long-lease behavior are both explicitly listed by
  this prompt as HIGH-risk categories ("perda de dados", "lock permanente",
  "recovery incorreto").
- Required fix: add a PID-reuse unit/integration test; add a
  `certification.long_running` package that runs past several heartbeat
  intervals and assert lease renewal in the report.
- Owner/component: `Agent.Windows/Process`, certification package set.

## MEDIUM

### M1 — Fleet explicit profile/capacity/capability publish unproven

Carried forward unchanged from `docs/agent-production-gap-review.md` and
`docs/agent-feature-matrix.md` — no new evidence either way. Dispatch
selection currently relies on heartbeat snapshot data only; explicit
publish-on-reconnect messages were never observed live. Impact: dispatch
may act on stale Fleet data after a long-lived reconnect. Owner:
`Agent.Application/Heartbeat`, `Agent.Application/Messaging`.

### M2 — Diagnostics export scrubbing only proven for the certification report path

`Certification.Core/Reporting/SecretScan.cs` is a real regex guard, but it
protects only `certification-runs/*/report.json`. Whether the Agent's
general diagnostics export (`Agent.Application/Diagnostics`) applies the
same scrubbing to bearer/session/execution tokens was not verified — the
folder exists but was not read line-by-line in this audit given time
constraints. Owner: `Agent.Application/Diagnostics`.

### M3 — No automated CI wiring found

No `.github/workflows` or equivalent CI configuration exists at the
repository root. All "PASS" evidence in every prior prompt's report came
from a human or an agent manually invoking `dotnet test` /
`docker compose exec ... python ...` / `certification.ps1`. There is no
regression safety net that runs on every change. Owner: repository
tooling/DevOps, outside Agent or Portal code itself.

### M4 — Uncommitted work spanning at least three prompts

`.git/logs/HEAD`'s last entry is 2026-08-06 ("PROMPT 2"). Every file this
audit found dated after that (certification harness, background
certification report, feature matrix, and the underlying code changes they
describe) exists only in the working tree, never committed. This is a
process risk (uncommitted work can be lost, and there is no commit-level
record of what "Prompt 4" actually changed) rather than a functional gap.
Owner: repository process, `git`.

## LOW

### L1 — Real Agent.Service launch harness process control

Unchanged from `docs/agent-production-gap-review.md` LOW item: sandboxed
process inspection cannot always classify inherited `dotnet` children.
`Certification.Core` already documents a fallback (`Process.Start` when the
native Win32 path throws) and always force-verifies process exit, so the
practical risk is manual-certification awkwardness, not orphaned processes
in the harness itself.

## OPTIONAL

### O1 — Simulator fault injection

Unchanged from the prior review: keep Portal Simulator-based fault
injection (lost ACK, duplicate command, latency, invalid messages,
reconnect, out-of-order delivery) as secondary coverage once H2 (live
replay) is closed.

## What this review does NOT claim

This review does not claim BLOCKER=0 at the product level once B1 (this
session's inability to execute anything) is set aside — B2's five Core
scenarios remain genuinely unproven, which is why the release gate in
final-certification-report.md is NOT APPROVED regardless of B1.
