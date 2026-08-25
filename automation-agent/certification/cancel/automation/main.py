"""
certification.cancel

Runs long enough for the harness to wait until the Portal observes RUNNING,
then request cancellation through POST /executions/{id}/cancel. The script
does not call the Agent or Portal directly; it only emits observable stdout
logs and progress markers while the real ExecutionHost/runtime process tree
is alive.
"""

from __future__ import annotations

import time

RUN_SECONDS = 60


def run(context: dict) -> dict:
    print("certification started")

    for elapsed in range(RUN_SECONDS):
        percentage = min(95, int((elapsed / RUN_SECONDS) * 100))
        print(f"progress {percentage}")
        print(f"cancel-wait tick {elapsed + 1}/{RUN_SECONDS}")
        time.sleep(1)

    print("certification completed without cancellation (unexpected)")
    return {"success": True, "cancelled": False}
