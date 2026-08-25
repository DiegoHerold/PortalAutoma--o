"""
certification.timeout

Runs longer than the manifest's execution_seconds (8s here) to exercise the
real timeout path:

  ExecutionManager.ExecuteAsync creates a linked CancellationTokenSource with
  CancelAfter(timeoutSeconds) (Agent.Application/Execution/ExecutionManager.cs).
  When it fires, ExecutionHost's own wait
  (Agent.ExecutionHost/Program.cs) observes OperationCanceledException and
  calls automationProcess.Kill(entireProcessTree: true) — a hard
  TerminateProcess on Windows, not a cooperative signal. There is currently
  no SIGTERM-then-SIGKILL style grace period delivered to the automation
  process itself; graceful_shutdown_seconds only bounds how long
  ExecutionHost waits to *confirm* the kill took effect.

Because the kill is immediate and not cooperative, this script does not
attempt to catch a termination signal — that would not reflect what actually
happens today. It just sleeps in small, observable increments so a human (or
the harness) inspecting logs/stdout.log can see how far execution got before
being killed. Uses time.sleep in a loop instead of one long sleep purely so
partial progress is visible if the process is inspected while still running.
"""

from __future__ import annotations

import time

RUN_SECONDS = 30
TICK_SECONDS = 1


def run(context: dict) -> dict:
    print("certification started")
    print(f"sleeping for {RUN_SECONDS}s against an 8s manifest timeout (expect a kill before completion)")

    for elapsed in range(RUN_SECONDS):
        print(f"tick {elapsed + 1}/{RUN_SECONDS}")
        time.sleep(TICK_SECONDS)

    # Should not be reached under a correctly enforced timeout.
    print("certification completed without being killed (unexpected)")
    return {"success": True, "timed_out": False}
