"""
certification.progress

Emits 0/20/40/60/80/100 at a configurable interval
(CERTIFICATION_PROGRESS_INTERVAL_SECONDS, default 1s). ExecutionHost mirrors
stdout lines shaped as "progress N" into execution.progress messages over
the real background pipe, so the Portal can observe intermediate progress
before the terminal event.
"""

from __future__ import annotations

import os
import time

STEPS = (0, 20, 40, 60, 80, 100)
INTERVAL_SECONDS = float(os.environ.get("CERTIFICATION_PROGRESS_INTERVAL_SECONDS", "1"))


def run(context: dict) -> dict:
    print("certification started")

    for step in STEPS:
        print(f"progress {step}")
        if step < 100:
            time.sleep(INTERVAL_SECONDS)

    print("certification completed")
    return {"success": True, "steps": list(STEPS)}
