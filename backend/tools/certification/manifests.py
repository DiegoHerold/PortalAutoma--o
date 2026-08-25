"""Builds the Portal Catalog `raw_manifest` YAML text for each certification
package.

This is a distinct schema from the package-internal `automation.json` files
under `automation-agent/certification/<name>/automation.json` (which the
Agent reads locally after downloading the package). The two are related but
not identical — see `modules/catalog/domain/manifest.py::parse_automation_manifest`
for the authoritative Portal-side grammar (entrypoint.type is hyphenated
here, e.g. "python-function", vs. underscored "python_function" in the
Agent-side package manifest) and
`automation-agent/src/Agent.Application/Validation/ManifestValidator.cs`
for the authoritative Agent-side grammar and its `ValidRuntimeIds` /
`ValidEntrypointTypes` allow-lists.

Both files must describe the same automation (matching `id`/`version`,
`runtime.id`/`runtime.version`, and the module/callable pair) — that
consistency is asserted by `tests/test_manifests.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

CERTIFICATION_CATEGORY_SLUG = "certification"
CERTIFICATION_CATEGORY_NAME = "Certification"

# Must stay in the Agent-side ValidRuntimeIds allow-list
# (automation-agent/src/Agent.Application/Validation/ManifestValidator.cs).
# "python-core-certification" (a dedicated certification-only runtime id)
# would fail Agent-side manifest validation with "Unknown runtime.id" — the
# harness deliberately reuses the real, already-supported "python-core"
# runtime instead of inventing one that breaks validation.
CERTIFICATION_RUNTIME_ID = "python-core"
CERTIFICATION_RUNTIME_VERSION = "3.13"


@dataclass(frozen=True)
class CertificationPackageSpec:
    package_id: str  # e.g. "certification.echo" — also the Automation.key
    name: str
    description: str
    version: str = "1.0.0"
    module: str = "automation.main"
    callable_name: str = "run"
    timeout_seconds: int = 60
    graceful_cancellation_seconds: int = 10
    capabilities: tuple[str, ...] = ("windows", "agent.background_execution")


CERTIFICATION_PACKAGES: tuple[CertificationPackageSpec, ...] = (
    CertificationPackageSpec(
        package_id="certification.echo",
        name="Certification Echo",
        description="Minimal real execution proof for the Portal-Agent certification harness.",
        timeout_seconds=60,
    ),
    CertificationPackageSpec(
        package_id="certification.fail",
        name="Certification Fail",
        description="Deterministic, safe failure used to certify the FAILED terminal path.",
        timeout_seconds=60,
    ),
    CertificationPackageSpec(
        package_id="certification.timeout",
        name="Certification Timeout",
        description="Deliberately exceeds its own timeout to certify the TIMED_OUT terminal path.",
        timeout_seconds=8,
        graceful_cancellation_seconds=5,
    ),
    CertificationPackageSpec(
        package_id="certification.cancel",
        name="Certification Cancel",
        description="Long-running background package used to certify Portal-initiated cancellation.",
        timeout_seconds=90,
        graceful_cancellation_seconds=10,
    ),
    CertificationPackageSpec(
        package_id="certification.progress",
        name="Certification Progress",
        description="Emits a 0/20/40/60/80/100 progress sequence to certify progress delivery.",
        timeout_seconds=60,
    ),
    CertificationPackageSpec(
        package_id="certification.artifact",
        name="Certification Artifact",
        description="Produces multiple artifacts of controlled size/type to certify the artifact lifecycle.",
        timeout_seconds=60,
    ),
)


def build_raw_manifest(spec: CertificationPackageSpec) -> str:
    """Build the Portal Catalog raw_manifest YAML text for one certification
    package, matching the grammar in modules/catalog/domain/manifest.py."""

    document = {
        "schema_version": 1,
        "id": spec.package_id,
        "name": spec.name,
        "version": spec.version,
        "description": spec.description,
        "category": CERTIFICATION_CATEGORY_SLUG,
        "runtime": {
            "id": CERTIFICATION_RUNTIME_ID,
            "version": CERTIFICATION_RUNTIME_VERSION,
        },
        "entrypoint": {
            "type": "python-function",
            "module": spec.module,
            "function": spec.callable_name,
            "path": "automation/main.py",
        },
        "execution": {
            "mode": "background",
            "timeout_seconds": spec.timeout_seconds,
            "graceful_cancellation_seconds": spec.graceful_cancellation_seconds,
        },
        "resources": {
            "cpu_units": 1,
            "memory_mb": 256,
            "disk_mb": 100,
        },
        "capabilities": {
            "required": list(spec.capabilities),
        },
    }
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def package_source_dir(spec: CertificationPackageSpec, certification_root: str) -> str:
    """Path to automation-agent/certification/<short-name>/ for this spec."""
    import os

    short_name = spec.package_id.split(".", 1)[1]
    return os.path.join(certification_root, short_name)
