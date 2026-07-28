"""
Background Python Example Automation

Receives a list via input, processes items, writes logs,
reports progress, generates result, and creates a text artifact.
"""

import json
import os
import sys
import time


def run(context: dict) -> dict:
    """Main entrypoint for the automation."""
    workspace = os.environ.get("AUTOMATION_WORKSPACE", ".")
    artifacts_path = os.environ.get("AUTOMATION_ARTIFACTS_PATH", os.path.join(workspace, "artifacts"))
    output_path = os.environ.get("AUTOMATION_OUTPUT_PATH", os.path.join(workspace, "output"))

    items = context.get("items", ["item_1", "item_2", "item_3", "item_4", "item_5"])
    total = len(items)

    print(f"Starting processing of {total} items")
    processed = []

    for i, item in enumerate(items, 1):
        print(f"Processing item {i}/{total}: {item}")
        time.sleep(0.5)  # Simulate work
        processed.append({"item": item, "status": "processed", "index": i})
        print(f"Progress: {i}/{total} ({100 * i // total}%)")

    # Create artifact
    report_path = os.path.join(artifacts_path, "processing_report.txt")
    with open(report_path, "w") as f:
        f.write(f"Processing Report\n")
        f.write(f"================\n\n")
        f.write(f"Total items: {total}\n")
        f.write(f"Processed: {len(processed)}\n\n")
        for p in processed:
            f.write(f"  [{p['index']}] {p['item']}: {p['status']}\n")

    print(f"Report written to {report_path}")

    result = {
        "processed": len(processed),
        "total": total,
        "items": processed
    }

    return result
