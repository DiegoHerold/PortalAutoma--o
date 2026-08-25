"""
certification.echo

Minimal real-execution proof for the Portal-Agent certification harness
(docs/certification-harness.md). This package is executed exactly like any
other automation: Portal -> Dispatch -> Agent WebSocket -> ExecutionManager ->
ExecutionHost -> this module. There is no certification-only shortcut inside
the Agent for this package.

ExecutionHost captures stdout lines and forwards them to Agent.Service over
the background named pipe. Lines in the form "progress N" are mirrored as
progress telemetry, and numeric entries under the returned "metrics" object
are mirrored as execution metrics before the terminal event is published.
"""

from __future__ import annotations

import os
import time

PROGRESS_STEPS = (0, 25, 50, 75, 100)
STEP_DELAY_SECONDS = float(os.environ.get("CERTIFICATION_STEP_DELAY_SECONDS", "0.2"))


def run(context: dict) -> dict:
    artifacts_path = os.environ.get(
        "AUTOMATION_ARTIFACTS_PATH",
        os.path.join(os.environ.get("AUTOMATION_WORKSPACE", "."), "artifacts"),
    )

    print("certification started")

    message = context.get("message", "Portal Agent Certification")
    print(f"input received: {message!r}")

    print("processing")
    for step in PROGRESS_STEPS:
        print(f"progress {step}")
        if step < 100:
            time.sleep(STEP_DELAY_SECONDS)

    os.makedirs(artifacts_path, exist_ok=True)
    artifact_path = os.path.join(artifacts_path, "result.txt")
    with open(artifact_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("Portal Agent Certification\n")
    print("artifact generated")

    print("certification completed")

    return {
        "received": message,
        "success": True,
        "metrics": {"items_processed": 1},
    }
