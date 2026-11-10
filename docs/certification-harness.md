# Certification Harness

Status: Prompt 4 updated. Infrastructure for deterministic, repeatable
Portal + Agent real-execution certification, with the background suite
certified in `docs/certification/background-certification-report.md`.

## 1. Objective

Give the next prompts a reproducible way to run:

```text
Portal real -> Gateway -> Dispatch -> Agent WebSocket -> Inbox
  -> Offer Handler -> Reservation -> Commit -> ExecutionManager -> ExecutionHost
```

without manual process babysitting, without a second "shortcut" path that
calls `ExecutionManager.ExecuteAsync()` directly, and without leaving
orphaned `dotnet`/Agent.Service processes behind — the exact problem
`docs/agent-production-gap-review.md` (Bloco 6) called out as
`Agent.Service bounded real startup = INCONCLUSIVE`.

The harness only *prepares, starts, observes, and stops* the real
components. It never bypasses Dispatch and never inserts an execution
directly into a database.

## 2. Environment prerequisites

The harness targets the same stack the rest of this repo already assumes:

- Windows (Agent.Service, ExecutionHost.exe, and Agent.Windows all use
  Windows-only APIs — DPAPI, WMI, Job Objects, named pipes with Windows ACLs).
- .NET 8 SDK (`dotnet --version` should report an 8.x SDK).
- The Portal installed with `scripts/portal.ps1 setup` (docs/deployment.md),
  whose `backend/.venv` runs `backend/tools/certification`.

None of this was available in the sandbox this harness was authored in (no
`dotnet`, no `docker`, Linux only, no outbound access to install either —
see "Verification status" below). The harness code itself was written,
read back carefully against the real production code it integrates with,
and exercised wherever Python tooling made that possible; the C# side
still needs a first `dotnet build` / `dotnet test` / manual
`certification start` pass on a real Windows dev machine before Prompt 4
relies on it.

## 3. Layout

```text
automation-agent/
  Certification.sln                      # standalone solution; does not touch AutomationAgent.sln
  tools/
    Certification.Core/                  # process supervisor, readiness, config, report model
    Certification.Cli/                   # `certification <command>` entry point
  certification/
    echo/       automation.json + automation/main.py
    fail/       automation.json + automation/main.py
    timeout/    automation.json + automation/main.py
    cancel/     automation.json + automation/main.py
    progress/   automation.json + automation/main.py
    artifact/   automation.json + automation/main.py
  certification-runs/                    # generated at runtime, gitignored
    agent-data/                          # isolated Agent data dir (item 8)
    run/                                 # PID files
    current/                             # live Agent.Service stdout/stderr logs
    cert_YYYYMMDD_NNN/                   # one directory per `run` invocation
      portal/ agent/ executions/ report.json

backend/
  tools/certification/
    api_client.py     # real Portal REST client (auth, catalog, fleet, executions)
    manifests.py       # builds the Portal Catalog raw_manifest YAML per package
    packaging.py        # deterministic package.zip builder
    seed.py              # idempotent Portal-side provisioning
    execution.py          # create/observe/wait-until-terminal via the real API
    cli.py                 # `python -m tools.certification.cli <subcommand>`
    tests/                  # pytest, runnable without a database

scripts/
  certification.ps1     # `.\scripts\certification.ps1 <command>` one-liner
```

Nothing here duplicates an existing tool. `backend/scripts/seed.py` seeds
admin/roles/categories for normal Portal bootstrap and is untouched;
`tools/certification/seed.py` is scoped to the six `certification.*`
automations only, reusing the same category endpoints.
`backend/gateway/agent_gateway/tests/smoke_*.py` remain the low-level
protocol smoke tests; the harness is a layer above them that drives a real
Agent.Service process instead of a synthetic WebSocket client.

## 4. Certification.Core

- `CertificationOptions` — every URL/path/timeout comes from environment
  variables (`CERTIFICATION_*`) with documented-dev-stack defaults, never a
  hardcoded machine-specific value (item 10).
- `Processes/NativeProcess.cs` — the one place that talks to Win32
  directly: launches Agent.Service with `CREATE_NEW_PROCESS_GROUP` so
  `GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid)` can request a real
  graceful shutdown later (the .NET Generic Host's `PosixSignalRegistration`
  is implemented via `SetConsoleCtrlHandler` on Windows, so this reaches
  the same shutdown path SIGTERM would trigger on Linux).
- `Processes/CertificationProcessSupervisor.cs` — start/wait/stop/kill/PID
  tracking/stale-process recovery. If the native launch path throws for any
  reason, it **falls back** to a plain `System.Diagnostics.Process.Start`
  (the same pattern already used by `ProcessTreeManager.cs` and
  `Agent.ExecutionHost/Program.cs` in this repo) and marks
  `SupportsGracefulStop = false` rather than silently pretending graceful
  shutdown is available. Either way, `StopAsync` always re-verifies the
  process actually exited and force-kills + records `ForcedTermination`
  if it did not — never leaves an orphan.
- `Portal/PortalHealth.cs`, `Portal/PortalAdminClient.cs`,
  `Portal/AgentReadinessEvaluator.cs` — health polling with a bounded
  timeout (never an infinite loop), and a readiness verdict built strictly
  from the real `GET /agents/{id}` payload
  (`connectivity_status`/`health_status`/`last_seen_at`, per
  `backend/modules/fleet/domain/agent.py`) — READY or DEGRADED both count
  as ready per item 12, nothing else does.
- `RuntimeProvisioning/RuntimeSeeder.cs` — see "Runtime provisioning" below.
- `Reporting/CertificationReport.cs` + `SecretScan.cs` — the report model
  and a last-resort regex guard that refuses to *write* a report containing
  anything that looks like a bearer token, password, or signed URL.

## 5. Certification.Cli

`certification <prepare|start|status|run|stop|clean>`, built as a normal
.NET console app (`automation-agent/tools/Certification.Cli`). Windows-side
orchestration (scripts/portal.ps1, Agent.Service process, readiness polling)
lives here in C#; Portal-side provisioning/execution/observation is
delegated to `backend/tools/certification/cli.py` via
`backend/.venv/Scripts/python -m tools.certification.cli ...` instead
of re-implementing the Portal HTTP contract twice.

| Command | What it does |
| --- | --- |
| `prepare` | Reuses a healthy stack (`portal.ps1 status`) or runs `portal.ps1 start`; waits for Portal/Gateway health; seeds the 5 `certification.*` automations/versions/packages through the real Portal API; ensures the `python-core`/`3.13` runtime is preseeded. |
| `start` | Requests a fresh registration token, launches Agent.Service with an isolated data directory and `DOTNET_ENVIRONMENT=Certification`, polls `GET /agents` until the certification Agent is READY/DEGRADED, writes a diagnostic dump automatically if it times out. |
| `status` | Read-only snapshot of Portal/Gateway/Agent/runtime/PID state. |
| `run <scenario\|background\|all>` | Creates a real execution via the Portal API for each requested `certification.*` scenario, polls until terminal, classifies PASS/FAIL/BLOCKED against the *expected* terminal state (never "not FAILED = PASS"), writes `report.json`. `background` and `all` currently run `echo`, `fail`, `timeout`, `cancel`, `progress`, and `artifact`. |
| `stop` | Graceful-then-forced shutdown of the supervised Agent.Service; records which path was used. |
| `clean` | Removes SQLite/downloads/staging/executions/spool from the isolated data dir; keeps the runtime store and `certification-runs/*/report.json` unless `--purge-runtime` / `--purge-reports` are passed (item 57, "preserve evidence"). |

## 6. Data directory isolation

`CertificationOptions.DataDirectory` defaults to
`automation-agent/certification-runs/agent-data` and is passed to
Agent.Service as `AUTOMATION_AGENT_DATA_DIR` — the exact environment
variable `AgentDirectoryResolver` already reads
(`automation-agent/src/Agent.Infrastructure/Storage/AgentDirectoryResolver.cs`).
That gives the certification Agent its own SQLite database, runtime store,
package store, downloads, staging, executions, artifacts, spool, and logs,
completely separate from any developer's normal
`C:\ProgramData\BiasonAutomationAgent`.

## 7. Identity and configuration

- `appsettings.Certification.json` (in `src/Agent.Service/`) is picked up
  automatically by the existing
  `AddJsonFile($"appsettings.{Environment.EnvironmentName}.json")` chain in
  `Program.cs` when `DOTNET_ENVIRONMENT=Certification` — no code change to
  `Agent.Service` was needed for this. It only sets non-host-specific
  values (display name, certification-sized pools, console logging).
- Portal URLs and the registration token are injected as
  `AUTOMATION_AGENT_Portal__ApiBaseUrl` / `__WebSocketUrl` /
  `__RegistrationToken` environment variables by `Certification.Cli` at
  launch time (the `AUTOMATION_AGENT_` prefix + `__` section separator is
  the existing convention documented directly in
  `PortalOptions.cs`) — never hardcoded, never written to a checked-in file.
- The Agent's internal `installation_id` is still an auto-generated GUID
  (`AgentIdentityRepository`, `automation-agent/src/Agent.Infrastructure/Persistence/AgentIdentityRepository.cs`)
  — there is no existing override hook for it, and adding one was out of
  scope for a config-only prompt. Isolation instead comes from the display
  name (`Agent:Name = "certification-agent-01"`, visible in Fleet) plus the
  separate data directory, which already gives the certification Agent a
  distinct, stable identity across restarts without touching a normal
  developer Agent's credentials.

## 8. Runtime provisioning ("Known Gaps")

Reading `Agent.Application/Messaging/Handlers/ExecutionOfferHandler.cs`
turned up a real, previously undocumented asymmetry:

- **Packages provision automatically.** `TryProvisionPackageAsync` inside
  the offer handler downloads and calls `IPackageStore.ImportAsync` the
  first time an offer references a package the Agent does not have yet.
  The certification harness relies on exactly this path — it does **not**
  preseed packages.
- **Runtimes do not.** Nothing in `ExecutionOfferHandler` (or anywhere else
  found while reading the Agent application layer) downloads a runtime on
  demand. `ExecutionManager.ExecuteAsync` just throws `"Runtime not
  found"` if `IRuntimeStore.GetPath` returns null. Until that gap is
  closed (a natural candidate for Prompt 4), the runtime genuinely has to
  be preseeded before the first certification execution.

`RuntimeProvisioning/RuntimeSeeder.cs` preseeds it by reusing the **real**
`Agent.Infrastructure/Stores/RuntimeStore.cs` (same SHA-256 verification,
same extraction, same SQLite artifact bookkeeping a Portal-triggered
download would produce) instead of copying files into the store directory
by hand. It needs a real Python 3.13 embeddable distribution for
`win-x64` — the repository cannot vendor that binary, so point
`CERTIFICATION_RUNTIME_ARCHIVE` at a locally downloaded
`python-3.13.x-embed-amd64.zip` (https://www.python.org/downloads/windows/)
before running `certification prepare`. Manifests use `runtime.id:
python-core`, matching `ManifestValidator.ValidRuntimeIds`
(`automation-agent/src/Agent.Application/Validation/ManifestValidator.cs`)
instead of inventing a `python-core-certification` id that would fail
Agent-side manifest validation outright.

## 9. A second, more important known gap: no live telemetry transport for background executions

While tracing how a running automation's logs/progress/metrics would reach
Portal, the trace turned up why
`docs/agent-production-gap-review.md` only marked that item "Partially
Ready":

- `Agent.ExecutionHost/Program.cs` launches the automation as a child
  process and forwards every stdout line, plus explicit
  `SendProgressAsync`/`SendMetricAsync` calls, over a named pipe
  (`Agent.ExecutionHost/Protocol/PipeClient.cs`) back to Agent.Service.
- For **interactive** executions, `SessionRunnerPipeServer.cs` and
  `InteractiveExecutionCoordinator.cs` run a real server on that pipe.
- For the **background** pool, Prompt 4 added the matching Agent.Service
  pipe pump. Real `ExecutionHost.exe` logs, progress markers, metrics, and
  terminal messages are normalized into ordered Portal telemetry.
- The six certification packages now exercise success, failure, timeout,
  cancel, progress, metrics, and multi-artifact upload through
  `.\scripts\certification.ps1 run background`.

<!-- Historical Prompt 3 analysis below is superseded by the Prompt 4 update above.
- For the **background** pool — what all five certification packages
  use — there is no equivalent server. `ProcessTreeManager.cs` launches
  ExecutionHost.exe and only ever reads its **exit code**; nothing listens
  on the `biason_agent_{executionId}_{attemptId}` pipe name it hands to
  the child. `Program.cs`'s own comment even treats a failed pipe connect
  as an expected, handled case ("Could not connect to Agent pipe,
  continuing without pipe communication").
- What Portal *does* reliably receive today for a background execution,
  per `Agent.Application/Execution/ResultCollector.cs`: the process exit
  code, `stderr.log` content (as `ErrorOutput`), `output/output.json`
  (the automation's return value), the `artifacts/` directory (the real,
  proven ACK-driven upload lifecycle from
  `docs/artifact-integration-report.md`), and ExecutionHost's own
  CPU/memory/duration metrics — all collected **after the process exits**,
  not streamed live.

The five certification packages are written around this reality instead of
around an imagined SDK:

- `certification.echo` puts its custom `items_processed` metric inside the
  returned result dict (so it travels through `output.json`, a channel
  that is proven to work), not as a live metric event.
- `certification.progress` still emits `0/20/40/60/80/100` on a real
  cadence to `stdout` (captured to `logs/stdout.log` in the workspace) so
  the gap between "logged" and "visible in Portal before completion" is
  directly observable by `certification run progress`, rather than
  assumed away.
- `certification.timeout`'s docstring documents that `ExecutionHost` kills
  the automation process immediately (`Process.Kill(entireProcessTree:
  true)`, a hard `TerminateProcess`) — there is no cooperative
  signal-then-grace-period delivered to the automation itself today.

Closing the background-pool telemetry gap (a `NamedPipeServerStream`
consumer symmetrical to the interactive path, or a stdout-marker parser
added to `CaptureOutputAsync`) is flagged here as the most consequential
piece of unfinished plumbing for Prompt 4, ahead of writing more
certification scenarios.
-->

## 10. Manifests

Two distinct, both real, schemas are involved:

- **Portal Catalog manifest** (`raw_manifest`, built by
  `backend/tools/certification/manifests.py`): YAML, hyphenated
  `entrypoint.type: python-function`, matches
  `backend/modules/catalog/domain/manifest.py::parse_automation_manifest`
  exactly (required fields, `execution.mode`/`timeout_seconds`,
  `resources.cpu_units/memory_mb/disk_mb`, `capabilities.required`).
- **Package-internal manifest** (`automation.json` inside each
  `automation-agent/certification/<name>/` package): underscored
  `entrypoint.type: python_function`, matches
  `Agent.Application/Validation/ManifestValidator.cs`'s
  `ValidEntrypointTypes`/`ValidRuntimeIds` allow-lists exactly (this is why
  `python-core-certification` was rejected in favor of `python-core`).

`backend/tools/certification/tests/test_manifests.py` asserts the second
schema's shape by hand (Python 3.10 in the authoring sandbox cannot import
`modules.catalog.domain.manifest` — it uses `enum.StrEnum`, Python 3.11+
only) but does round-trip every generated manifest through `yaml.safe_load`
and check every field `parse_automation_manifest` requires. Re-run it
with the backend virtualenv (Python 3.12) for the authoritative check.

## 11. Packages are content-addressed

`backend/tools/certification/packaging.py` zips
`automation-agent/certification/<name>/` with a fixed file order and fixed
zip timestamps, excluding `__pycache__`/`.git`/etc. (same exclusion list
`docs/automation-package.md` documents for `build_package`). The same
source always produces the same SHA-256 — verified directly, see
"Verification status" below.

## 12. Seed idempotency

`backend/tools/certification/seed.py` looks up categories by slug,
automations by key, automation versions by version string, and runtimes/
runtime versions by key/version before creating anything — running
`certification prepare` twice does not duplicate them. An
`AutomationVersion` already in `published` status is left untouched
(package upload is skipped entirely) rather than re-uploaded.

## 13. Report

`CertificationReport.Save()` writes
`certification-runs/cert_YYYYMMDD_NNN/report.json` with Portal/Storage/
Gateway/Runtime/Agent status and one `ScenarioResult` per requested
scenario, `Status` always one of `PASS/FAIL/BLOCKED/NOT_APPLICABLE` — a
harness-side wait timeout is reported as `BLOCKED`, never silently upgraded
to `PASS` (`OverallGate` is `PASS` only if every scenario is `PASS`, `FAIL`
if any scenario is `FAIL`, `BLOCKED` otherwise). `SecretScan` refuses to
write the file at all if the serialized JSON matches a bearer-token/
password/signature-shaped pattern.

## 14. Commands

```powershell
.\scripts\certification.ps1 prepare
.\scripts\certification.ps1 start
.\scripts\certification.ps1 status
.\scripts\certification.ps1 run echo
.\scripts\certification.ps1 run background
.\scripts\certification.ps1 stop
.\scripts\certification.ps1 clean
.\scripts\certification.ps1 full          # prepare -> start -> run background -> stop
```

Equivalent direct .NET invocation, if you are not on Windows PowerShell:

```bash
dotnet run --project automation-agent/tools/Certification.Cli -- prepare
dotnet run --project automation-agent/tools/Certification.Cli -- start
dotnet run --project automation-agent/tools/Certification.Cli -- run background
dotnet run --project automation-agent/tools/Certification.Cli -- stop
```

## 15. Historical Prompt 3 verification status

Prompt 4 live Windows/Portal verification is recorded in
`docs/certification/background-certification-report.md`.

This harness was authored in a Linux-only sandbox with no `dotnet`, no
`docker`, and no outbound access to install either (confirmed:
`dot.net`/`dotnetcli.azureedge.net` blocked by the environment's network
allowlist; `apt-get install postgresql/dotnet-sdk` blocked — no root).
PyPI/npm access *was* available.

Actually executed in this session:

- All 5 certification package `main.py` scripts, directly, with real
  workspace directories — `certification.echo`, `.fail`, `.artifact`
  produced exactly the described output/artifacts; `.progress` produced
  the full `0/20/40/60/80/100` sequence; `.timeout`'s loop structure was
  reviewed (not run to completion, since its point is to be killed by
  ExecutionHost, which does not exist in this sandbox).
- `backend/tools/certification/packaging.py` — built all 5 packages,
  confirmed deterministic SHA-256 across repeated builds, confirmed
  `__pycache__`/`.pyc` exclusion, confirmed `automation.json` +
  `automation/main.py` are the only archive members (matching
  `PackageStore.FindManifest` and `RuntimeLauncher.BuildPythonFunction`).
- `backend/tools/certification/manifests.py` — generated and structurally
  validated all 5 Portal Catalog manifests against
  `parse_automation_manifest`'s documented grammar.
- `backend/tools/certification/tests/` (`test_manifests.py`,
  `test_packaging.py`, `test_api_client.py`) — **12/12 passed** via
  `python -m pytest tools/certification/tests -q` (api_client tests use
  `httpx.MockTransport`, no live Portal required).

Not executed in this session (no environment for it):

- `dotnet build`/`dotnet test` on `Certification.sln` or
  `AutomationAgent.sln`.
- `docker compose up` and any live Portal HTTP call.
- Launching a real `Agent.Service` process, `certification start`,
  `certification run`, or any live Portal E2E scenario.
- `NativeProcess.cs`'s Win32 `CreateProcess`/`GenerateConsoleCtrlEvent`
  path specifically — the highest-risk, least-verifiable piece of this
  delivery (see the runbook's troubleshooting section).

**The mandatory first step on a real Windows dev machine is `dotnet build
automation-agent\Certification.sln`**, followed by
`dotnet test automation-agent\Certification.sln` and a manual
`certification prepare && certification start && certification status`
pass, exactly as docs/runbooks/portal-agent-certification.md walks
through.

## 16. Troubleshooting

- **`scripts/portal.ps1 not found`** — run from inside the repo, or set
  `CERTIFICATION_REPO_ROOT`.
- **`prepare` reports Portal NOT READY** — run `.\scripts\portal.ps1 status`
  and check the logs listed in docs/deployment.md.
- **`start` times out with Agent state `Registered` (not `Ready`)** — the
  Agent registered but never reported `connectivity_status = online` in
  Fleet; check the diagnostic dump written under
  `certification-runs/current/agent/diagnostic-dump.json` and the Agent's
  own Serilog file under its isolated `logs/` directory for WebSocket
  connect errors.
- **`start` times out and the process already exited** — check
  `certification-runs/current/agent/agent-service.stderr.log` first; a
  missing/invalid `RegistrationToken` or an `Options.ValidateOnStart()`
  failure both show up there immediately.
- **`stop` reports `Forced=true` every time** — expected if
  `NativeProcess.Start` fell back to `Process.Start` (no graceful-stop
  support) — check the `certification-cli` console log for the fallback
  warning logged at `start` time. If it *did* use the native path and
  still always force-kills, that is the one Win32 code path this session
  could not verify — start by confirming `GenerateConsoleCtrlEvent`
  actually returns `true` for the certification Agent's PID (add a
  temporary log line) before assuming Agent.Service itself is not
  reacting to `CTRL_BREAK`.
