# Artifact Integration Report

Status: READY for Prompt 3.

## 1. Portal Contract

The real Portal artifact contract is ACK-driven:

```text
artifact.created -> portal.ack(result.upload_url, result.upload_session_id)
HTTPS PUT upload_url
artifact.uploaded -> portal.ack(result.status = available)
```

The Portal gateway accepts `artifact.created`, `artifact.uploaded`, and `artifact.failed` from the Agent. `artifact.created` calls Storage `InitiateArtifactUpload`, persists the artifact, stored object, and upload session, then returns upload instructions in `portal.ack.payload.result`. `artifact.uploaded` calls `CompleteArtifactUpload`, checks that the uploaded object exists, validates size and SHA-256, and marks the artifact `available`.

Upload URLs point to the Portal storage proxy endpoint:

```text
/api/v1/artifacts/uploads/{upload_session_id}/bytes
```

The Agent does not need to know whether the backing storage is local package storage, MinIO, or another object provider.

## 2. Previous Agent Contract

Before this change, the Agent persisted `artifact.created` in the outbox but did not use its `portal.ack`. The upload manager then started a second REST-style flow:

```text
RequestArtifactUploadAsync
UploadArtifactContentAsync
ConfirmArtifactUploadAsync
```

That path diverged from the Portal gateway contract and could not prove the official `artifact.created -> ACK -> PUT -> artifact.uploaded` lifecycle.

## 3. Mismatch

The mismatch was:

- Portal produced upload instructions through `portal.ack`.
- Agent ignored those instructions.
- Agent asked for another upload target through a REST initiate call.
- Agent confirmed through REST instead of sending `artifact.uploaded`.
- Duplicate `artifact.created` or `artifact.uploaded` with the same `message_id` did not return the original artifact result on the Portal duplicate path.

## 4. Changes

Agent:

- Added persisted ACK correlation fields to `pending_artifacts`.
- Added `ArtifactAcknowledgementHandler`.
- Extended `PortalMessageAcknowledgementService` to delegate artifact ACKs by looking up the original outbox message.
- Replaced `ArtifactUploadManager` main path with ACK-driven upload.
- Added `IArtifactContentUploader` and `ArtifactContentUploader` for streaming HTTPS upload.
- Added official payloads for `artifact.uploaded` and `artifact.failed`.
- Added upload timeout and confirmed-local-retention options.
- Added path-shape validation before upload.

Portal:

- Duplicate `artifact.created`, `artifact.uploaded`, and `artifact.failed` now re-run the idempotent Storage handler and return a deterministic `result` in the duplicate `portal.ack`.
- The telemetry/artifacts smoke now verifies duplicate `artifact.created` and duplicate `artifact.uploaded`.
- Storage `InitiateArtifactUpload` now creates a fresh upload session for an existing non-available artifact when the previous upload session is expired.

## 5. State Machine

Agent state mapping:

```text
Pending              local legacy/discovered state
Announced            artifact.created persisted in outbox
UploadUrlReceived    portal.ack supplied upload instructions
Uploading            HTTPS PUT in progress
Uploaded             PUT succeeded, artifact.uploaded persisted in outbox
Confirmed            Portal ACK confirmed artifact available
RetryWait            transient upload failure or interrupted upload
Failed               definitive local/upload failure reported through artifact.failed
```

Portal state mapping remains the existing Storage lifecycle:

```text
created -> uploading -> available
failed
```

## 6. Retry Policy

Transient upload failures use `RetryWait`:

- HTTP 408, 429, and 5xx are retryable.
- `HttpRequestException`, timeout, and IO failures are retryable.
- Attempt count is persisted.
- Delay uses the existing configured base delay multiplied by attempt count.
- Maximum attempts remains configurable.

Definitive local validation failures publish `artifact.failed`.

## 7. Recovery

Recovery behavior:

- `Pending` without announcement message: enqueue `artifact.created`.
- `Announced`: wait for outbox replay/ACK.
- `UploadUrlReceived`: upload service resumes PUT.
- `Uploading`: move to `RetryWait`.
- `Uploaded`: re-enqueue `artifact.uploaded` with stable message id.
- `Confirmed`: no upload.
- `Failed`: no upload.

## 8. Security And Retention

The Agent:

- Does not log upload URLs.
- Does not include upload URLs in sync payloads.
- Persists upload URL only in local SQLite for restart recovery.
- Validates before PUT that the announced relative name maps to a local file under an `artifacts` directory.
- Rejects rooted names, `.`/`..` path segments, mismatched local paths, and reparse-point files.
- Revalidates size and SHA-256 immediately before upload.
- Uses configurable upload timeout.
- Uses configurable confirmed local retention; default `0` preserves current cleanup-after-confirmation behavior.

## 9. Test Evidence

Baseline before implementation:

- `dotnet test .\automation-agent\AutomationAgent.sln`: PASS, 269 tests.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_gateway_flow.py`: PASS.
- `docker compose exec backend python modules/orchestration/tests/smoke_execution_dispatch_flow.py`: PASS.
- `docker compose exec backend python modules/telemetry/tests/smoke_telemetry_completion_artifacts.py`: PASS.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_sync_state.py`: PASS.

Final evidence:

- `dotnet test .\automation-agent\AutomationAgent.sln`: PASS, 277 tests.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_gateway_flow.py`: PASS.
- `docker compose exec backend python modules/orchestration/tests/smoke_execution_dispatch_flow.py`: PASS.
- `docker compose exec backend python gateway/agent_gateway/tests/smoke_sync_state.py`: PASS.
- `docker compose exec backend python modules/telemetry/tests/smoke_telemetry_completion_artifacts.py`: PASS.

The telemetry/artifacts smoke uses real Portal storage upload and download. Test artifact:

```text
content: "artifact smoke payload\n"
size: 23
sha256: 3aad204e5ba07035e04173aefab5127fab1a415532b471a5eb0cdeb6dfd7d83e
storage verification: byte-for-byte MATCH
```

## 10. Gate Matrix

```text
artifact.created                   PASS
Portal ACK upload instructions     PASS
ACK correlation                    PASS
HTTPS upload                       PASS
artifact.uploaded                  PASS
Portal confirmation                PASS
retry                              PASS
restart recovery                   PASS
duplicate created                  PASS
duplicate uploaded                 PASS
hash validation                    PASS
missing file handling              PASS
path validation                    PASS
upload URL expired refresh         PASS
multiple artifacts                 PASS
real storage object verification   PASS
```

## 11. Remaining Gaps

No blocker remains for the artifact lifecycle.

Known follow-up hardening:

- Add full live Agent process restart during an in-flight large upload.
- Add a larger streaming artifact smoke in CI when runtime budget is defined.
- Add queue metrics/export artifacts-summary files in the broader diagnostics package.
- Define manifest-level required vs optional artifact policy.
- Define execution finalization policy if future workflows require artifacts confirmed before terminal success.
