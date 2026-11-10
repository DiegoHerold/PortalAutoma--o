# Runbook: Portal-Agent Certification

See `docs/certification-harness.md` for design/rationale. This is the
step-by-step.

## 0. Prerequisites (once per machine)

1. Windows 10/11, .NET 8 SDK, Portal installed with `.\scripts\portal.ps1 setup`.
2. Clone/open this repo.
3. Download a Python 3.13 embeddable package for Windows x64 from
   https://www.python.org/downloads/windows/ ("Windows embeddable package
   (64-bit)"). Keep the `.zip` — do not extract it. This is the only binary
   the harness cannot provide for you (see certification-harness.md, section 8).

## 1. First run

```powershell
cd <repo-root>
$env:CERTIFICATION_RUNTIME_ARCHIVE = "C:\path\to\python-3.13.x-embed-amd64.zip"
.\scripts\certification.ps1 prepare
```

Expected: Portal/Gateway/Storage/Runtime all report READY, and the seed
step lists `certification.echo` / `.fail` / `.timeout` / `.cancel` /
`.progress` / `.artifact` each with `status: published`.

If anything reports NOT READY or BLOCKED, stop here — see
certification-harness.md "Troubleshooting" before continuing.

## 2. Build and test the harness itself

```powershell
cd automation-agent
dotnet build Certification.sln
dotnet test Certification.sln
cd ..
```

This is the step that could not be run in the environment this harness was
authored in (no Windows, no dotnet — see certification-harness.md section
15). Do this before trusting `certification start`/`run`.

## 3. Start the certification Agent

```powershell
.\scripts\certification.ps1 start
```

Expected console output ends with a line like:

```text
Agent READY. agent_id=agt_xxxxx connectivity=online health=healthy last_seen=...
```

If it times out, a diagnostic dump is written automatically to
`automation-agent/certification-runs/current/agent/diagnostic-dump.json` —
read it before retrying.

## 4. Confirm status independently

```powershell
.\scripts\certification.ps1 status
```

Expected:

```text
Portal:  READY (...)
Gateway: READY (...)
Agent registered: YES
Agent online:      YES
Agent state:       Ready
Last heartbeat:    <a few seconds ago>
Runtime (python-core/3.13): READY
Agent.Service PID file: <pid>
```

## 5. Run the certification.echo scenario alone first

```powershell
.\scripts\certification.ps1 run echo
```

This is the smallest possible real E2E: Portal creates the execution,
Dispatch offers it to the real Agent, the real Agent runs a real
`python.exe automation/main.py` under ExecutionHost.exe, and the harness
polls `GET /executions/{id}` until it reaches `succeeded`. Expected:

```text
Run ID: cert_YYYYMMDD_NNN
  certification.echo       Pass
Overall gate: PASS
Report: automation-agent/certification-runs/cert_YYYYMMDD_NNN/report.json
```

If this does not PASS, do not proceed to the rest of the suite — diagnose
this one scenario first (it is the minimum viable proof the whole chain
works at all).

## 6. Run the full suite

```powershell
.\scripts\certification.ps1 run background
```

Expected: `certification.echo`, `.fail`, `.timeout`, `.cancel`,
`.progress`, and `.artifact` all report `Pass`. `run all` is currently an
alias for the same background suite.

## 7. Stop cleanly

```powershell
.\scripts\certification.ps1 stop
```

Confirm no `AgentService`/`ExecutionHost` process remains in Task Manager.
The console log reports whether the shutdown was graceful or forced.

## 8. Clean up (optional)

```powershell
.\scripts\certification.ps1 clean                 # keeps runtime store + reports
.\scripts\certification.ps1 clean -PurgeRuntime    # also drops the imported runtime
.\scripts\certification.ps1 clean -PurgeReports    # also deletes certification-runs/cert_*/
```

## 9. One-line full run

```powershell
.\scripts\certification.ps1 full
```

Runs prepare -> start -> run background -> stop in sequence, stopping early (and
leaving Agent.Service running for inspection) if `prepare` or `start`
fails.

## Reproducing exactly what Prompt 4 asked for

```powershell
.\scripts\certification.ps1 prepare
.\scripts\certification.ps1 start
.\scripts\certification.ps1 status
.\scripts\certification.ps1 run background
.\scripts\certification.ps1 stop
```
