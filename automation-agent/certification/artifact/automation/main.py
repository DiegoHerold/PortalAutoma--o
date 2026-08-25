"""
certification.artifact

Produces three artifacts of controlled, deterministic size and content:

  small.txt       - a few dozen bytes of text
  result.json     - a small structured JSON document
  binary-test.bin - deterministic pseudo-random binary content

All three are written under $AUTOMATION_ARTIFACTS_PATH. ResultCollector
(Agent.Application/Execution/ResultCollector.cs::CollectArtifactsAsync)
walks that directory after the process exits, computes a SHA-256 for each
file and hands the list to ExecutionManager, which is what ultimately drives
the real artifact.created -> portal.ack -> HTTPS PUT -> artifact.uploaded
lifecycle documented in docs/artifact-integration-report.md. Nothing here
talks to the Agent or Portal directly — the package only has to produce
files in the right place.
"""

from __future__ import annotations

import hashlib
import json
import os

BINARY_SIZE_BYTES = 4096


def _deterministic_binary(size: int) -> bytes:
    # Deterministic, dependency-free pseudo-random bytes: repeated SHA-256
    # digest of an increasing counter. Same output on every run, which
    # keeps the certification.artifact package reproducible for hash
    # comparisons in the harness's observation step.
    out = bytearray()
    counter = 0
    seed = b"certification.artifact"
    while len(out) < size:
        counter += 1
        out.extend(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
    return bytes(out[:size])


def run(context: dict) -> dict:
    artifacts_path = os.environ.get(
        "AUTOMATION_ARTIFACTS_PATH",
        os.path.join(os.environ.get("AUTOMATION_WORKSPACE", "."), "artifacts"),
    )
    os.makedirs(artifacts_path, exist_ok=True)

    print("certification started")

    small_path = os.path.join(artifacts_path, "small.txt")
    with open(small_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("Portal Agent Certification - small text artifact\n")
    print(f"wrote {small_path}")

    result_payload = {
        "package": "certification.artifact",
        "artifacts": ["small.txt", "result.json", "binary-test.bin"],
        "binary_size_bytes": BINARY_SIZE_BYTES,
    }
    json_path = os.path.join(artifacts_path, "result.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result_payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"wrote {json_path}")

    binary_content = _deterministic_binary(BINARY_SIZE_BYTES)
    binary_path = os.path.join(artifacts_path, "binary-test.bin")
    with open(binary_path, "wb") as handle:
        handle.write(binary_content)
    print(f"wrote {binary_path} ({len(binary_content)} bytes, "
          f"sha256={hashlib.sha256(binary_content).hexdigest()})")

    print("certification completed")

    return {
        "success": True,
        "artifact_count": 3,
        "binary_sha256": hashlib.sha256(binary_content).hexdigest(),
    }
