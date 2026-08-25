# Background Certification Report

Status: READY for real background execution.

Date: 2026-08-14
Run: `cert_20260814_017`
Command: `.\scripts\certification.ps1 run background`
Gate: `PASS`

## Scope

Certified path:

`Portal real -> Dispatch -> Agent Gateway -> Agent.Service real -> Inbox -> OfferHandler -> Admission -> Reservation -> execution.accepted -> Portal -> execution.commit -> Agent.Service -> CommitHandler -> ExecutionManager -> ExecutionHost.exe real -> python-core/3.13 runtime -> package automation -> logs/progress/metrics/result/artifacts -> Portal`.

The run did not use manual offer injection, direct `ExecutionManager` calls, direct database mutation to advance state, mocks, or synthetic Agent clients.

## Environment

| Component | Evidence |
| --- | --- |
| Portal | `GET /api/v1/health` returned `{"status":"ok","app":"Portal Automacoes API"}` before the run. |
| Gateway | `agent-gateway/health` returned HTTP 200 before the run. |
| Agent | `certification-agent-01`, `agent_id=agt_CI0ZDEZtkhgWt1INDFEj7Bh`, online, `Agent state: Ready`. |
| Agent process | `Agent.Service` started by certification harness; status showed PID file `47436`. |
| Runtime | `python-core/3.13` present in the Agent runtime store. |
| Execution host | Agent logs show real `ExecutionHost` PIDs launched for the suite, including `34716`, `45220`, `26864`, `36484`, and `47920`. |

Note: the JSON report fields `Portal`, `Gateway`, `Storage`, `Runtime`, `AgentServiceStartupPass`, and `GracefulShutdownPass` are not populated by the `run` command path and remained default `false`. The readiness evidence above came from the independent `status` command and the real Portal observations.

## Scenario Results

| Scenario | Execution | Attempt | Portal status | Events / ACK | Evidence |
| --- | --- | --- | --- | --- | --- |
| `certification.echo` | `exe_339081b0ff014092878e5c141ed233ad` | `att_7e7fe566d3c74dcca27e07a0f4e60768` | `succeeded` | 21 events, seq 1..21, no gaps, ACK 21 | Artifact `result.txt` available, size 27, sha256 `585ac59560dc5abd90f73ef75ce8082f737629b5a19b291a4e129f83c3055d1f`. |
| `certification.fail` | `exe_5068e00c88cb42e48ae9d2d5b1f8ecd2` | `att_70755ebeb9be433db15fd53887d57e7c` | `failed` | 17 events, seq 1..17, no gaps, ACK 17 | Intentional failure surfaced as Portal failure. |
| `certification.timeout` | `exe_d8fe4c2682ea423c8d12f7c1fcec3343` | `att_318b6eb3a3af44c6b6190342240ce1c9` | `timed_out` | 21 events, seq 1..21, no gaps, ACK 21 | Timeout terminal event reached Portal. |
| `certification.cancel` | `exe_40539d3b97ef48c38a4fca28ae8753e8` | `att_83abf89333364d3f87421ea8c3787ba6` | `cancelled` | 20 events, seq 1..20, no gaps, ACK 20 | Portal cancel API used; cancellation request status `completed`. |
| `certification.progress` | `exe_8a6d451347a04cfab07a5f74c02b615d` | `att_ae4ea1edd4cd4a8b9382fc8f73371190` | `succeeded` | 23 events, seq 1..23, no gaps, ACK 23 | Progress and 13 metric rows persisted. |
| `certification.artifact` | `exe_e17341849d634f5dab0241fba7c73468` | `att_1bdd518cfea347628732c3eb36abb65c` | `succeeded` | 10 events, seq 1..10, no gaps, ACK 10 | Three artifacts available: `binary-test.bin`, `result.json`, `small.txt`. |

Artifact hashes from the real Portal records:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `binary-test.bin` | 4096 | `d3d8144304918e5a0953fb83b7c8ecb228d830a0afd5a514f486165a93b07502` |
| `result.json` | 151 | `5c6429d203e43872e096d591bbc81cd1b32b4b53e570f7649bc78c8f3d3f7dbd` |
| `small.txt` | 49 | `3be3f61ac0b3ab16a8e3923394960d466da7e3dc982b5257e9cd6da7cf081d60` |

## Fixes Applied During Certification

| Area | Fix |
| --- | --- |
| Gateway envelopes | `portal.ack`, `portal.error`, `portal.disconnect`, and `agent.connected` now use complete versioned envelopes and UTC `Z` timestamps. |
| Runtime launch | `ExecutionHost` launch now resolves the real host path, passes package/runtime/workspace paths, and bootstraps Python with package import path and input/output env. |
| Host telemetry | Added pipe pump from real `ExecutionHost` to Agent outbox for logs, progress, metrics, and terminal payloads. |
| Event ordering | Added per-attempt `ExecutionAttemptSequenceTracker`; host metrics/progress/logs and terminal messages use contiguous sequences. |
| Result payloads | Terminal completed/failed/timed-out/cancelled payloads include execution id, attempt id, output/result, error message, exit code, timestamps, and resource usage where available. |
| Failure observation | Certification observation now extracts errors from real Portal attempt/execution/result fields. |
| Cancel scenario | Added `certification.cancel`, Portal wait-for-running, idempotent cancel calls, and expected `cancelled` classification. |
| Cancel delivery | Removed the separate running-state `execution.cancelling` telemetry event so terminal `execution.cancelled` is not blocked behind auxiliary telemetry. |
| Cancellation request lifecycle | Gateway marks the active `cancellation_request` as `completed` when real terminal `execution.cancelled` is applied. |
| Local lease cleanup | Agent now marks the local execution lease `released` when the committed attempt reaches any terminal path, preventing the local renewal scanner from later marking already-terminal executions as lease-lost. |

## Verification Commands

Passed:

- `dotnet build automation-agent\src\Agent.Service\Agent.Service.csproj --no-restore`
- `dotnet build automation-agent\src\Agent.ExecutionHost\Agent.ExecutionHost.csproj --no-restore`
- `dotnet build automation-agent\tools\Certification.Cli\Certification.Cli.csproj --no-restore`
- `dotnet test automation-agent\tests\Certification.Tests\Certification.Tests.csproj --no-restore`
- `dotnet test automation-agent\tests\Agent.IntegrationTests\Agent.IntegrationTests.csproj --no-restore --filter "FullyQualifiedName~ExecutionOfferAndCommitTests"`
- `dotnet test automation-agent\tests\Agent.IntegrationTests\Agent.IntegrationTests.csproj --no-restore --filter "FullyQualifiedName~ExecutionOfferAndCommitTests|FullyQualifiedName~OutboxInboxTests|FullyQualifiedName~ExecutionCancelTests"`
- `dotnet test automation-agent\tests\Agent.UnitTests\Agent.UnitTests.csproj --no-restore --filter "FullyQualifiedName~ExecutionManagerTests|FullyQualifiedName~PipeClientTests|FullyQualifiedName~RuntimeLauncherTests"`
- `docker compose exec -T backend python -m compileall tools/certification`
- `docker compose exec -T backend python -m compileall gateway/agent_gateway/message_router.py gateway/agent_gateway/tests/test_cancellation_request_completion.py`
- `docker compose exec -T backend python -c "... cancellation request completion tests passed ..."`
- `.\scripts\certification.ps1 run echo`
- `.\scripts\certification.ps1 run fail`
- `.\scripts\certification.ps1 run timeout`
- `.\scripts\certification.ps1 run cancel`
- `.\scripts\certification.ps1 run background`

Not run as pytest: `pytest` is not installed in the backend container, so backend pytest modules were validated with `compileall` and direct Python invocation for the new regression.

## Incidents And Resolution

| Incident | Resolution |
| --- | --- |
| `cert_20260814_010` fail scenario reached Portal `failed`, but harness marked Fail because error extraction looked at the wrong fields. | Added extraction from attempt/execution/result error fields; rerun `cert_20260814_012` passed. |
| `cert_20260814_011` hit a transient Postgres deadlock while creating an execution attempt. | Rerun passed; recorded as a Portal/DB concurrency gap, not an Agent execution failure. |
| `cert_20260814_014` cancel reached local terminal but Portal later forced cancellation because an intermediate telemetry event blocked terminal ACK. | Removed the auxiliary running-state cancelling event and completed cancellation requests on terminal cancel; reruns `cert_20260814_016` and `cert_20260814_017` passed. |
| Agent logs showed local lease renewal later marking already-terminal executions as lost. | Terminal commit handling now releases the local lease for success, failure, timeout, cancellation, and commit-time failure; integration tests assert terminal leases are no longer returned by `GetNonFinalAsync()`. |

## Remaining Scope Outside Prompt 4

Not certified by this background gate:

- Browser execution.
- Interactive execution and Session Runner behavior.
- Multi-agent dispatch and fairness.
- Agent/Portal restart during active execution.
- UI streaming latency for logs/progress/metrics.
- Long-running lease renewal beyond the current short timeout/cancel scenarios.

These remain separate certification tracks and do not block the Prompt 4 background certification result.
