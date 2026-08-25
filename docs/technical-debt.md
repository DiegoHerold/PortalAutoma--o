# Technical Debt

Status: Prompt 7 audit, 2026-08-20. Non-blocking items only — anything that
gates the release gate lives in `docs/certification/final-production-gap-review.md`
instead.

## Process debt

- **No CI pipeline.** No `.github/workflows` or equivalent found. Every PASS
  claim in this repository's history was produced by a human or an agent
  running commands by hand. Recommend wiring at minimum `dotnet test
  AutomationAgent.sln` and the backend `compileall`/smoke scripts into CI so
  regressions surface automatically instead of depending on the next prompt
  remembering to re-run things by hand.
- **~2 weeks of uncommitted work.** `.git/logs/HEAD` stops at 2026-08-06
  ("PROMPT 2"). The certification harness, the background certification
  report, and the current feature matrix (all dated ≈2026-08-14) exist only
  in the working tree. Recommend committing in reviewable slices rather than
  letting prompt-sized batches of work sit uncommitted.
- **Backend container has no `pytest`.** `background-certification-report.md`
  notes new backend regression checks had to be validated with
  `python -m compileall` and manual `python -c "..."` invocation instead of
  `pytest`, because `pytest` is not installed in the backend container. This
  weakens the reliability of "automated test" claims for backend-side
  certification code.

## Code/architecture debt

- **Dual manifest schemas by design.** The Portal Catalog manifest
  (`raw_manifest`, hyphenated `entrypoint.type: python-function`) and the
  package-internal manifest (`automation.json`, underscored
  `entrypoint.type: python_function`) are two different, intentionally
  separate schemas per `docs/certification-harness.md` §10. This is
  documented and deliberate, but it is an easy place for a future author to
  introduce a manifest that validates against one schema and silently fails
  the other. Consider a shared schema-conversion helper instead of two
  hand-written builders.
- **`installation_id` has no override hook.** Per
  `docs/certification-harness.md` §7, the Agent's `installation_id` is
  always an auto-generated GUID (`AgentIdentityRepository`); certification
  isolation instead relies on a distinct display name and data directory.
  Fine for now, but will need a real override hook once multiple Agents per
  machine or reproducible identity across reinstalls matters (Fase 3
  territory).
- **Certification.sln is a second solution file.** `automation-agent/Certification.sln`
  is deliberately kept separate from `AutomationAgent.sln` "to not touch"
  the main solution. This means two solutions must be kept in sync by hand
  as projects are added/renamed; worth revisiting once the harness
  stabilizes.
- **Legacy `Worker`/`Job`/`Execution` naming still present**, per
  `AGENTS.md` and `README.md`, as an intentional compatibility layer during
  the ongoing migration to `Agent`/`Execution`/`TaskExecution`/
  `ExecutionAttempt`/`ExecutionOffer`. Tracked already in `docs/migration.md`
  — flagged here only so it isn't lost in the Fase 2 closeout.
- **`execution.cancel_requested` kept as a legacy/semantic-only name**
  (`docs/portal-agent-protocol-matrix.md`) while the real wire message is
  `execution.cancel`. Low risk, but another naming trap for a future
  contributor grepping for the wrong string.

## Test debt

- **No PID-reuse test.** See `final-production-gap-review.md` H4 — this is
  scored HIGH there because it is explicitly mandated by this prompt, but
  it is also a general testing gap independent of Fase 2 timing.
- **No dedicated adversarial/security test suite.** See H3 in the gap
  review. Restating here because even after H3 is closed for release-gate
  purposes, ongoing maintenance of that suite as new attack surface is
  added (new message types, new artifact kinds) is itself debt to track.
