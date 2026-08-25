"""Idempotent Portal-side provisioning for the certification packages.

Ensures, through the real Portal API only (no direct DB writes):

  * a "certification" category exists
  * the "python-core" / "3.13" runtime version exists and is published
  * each certification.* automation + its 1.0.0 version exists
  * the version's package (zip built from automation-agent/certification/<name>/)
    is uploaded and the version is published on the "development" channel
    equivalent (this Portal build does not have a separate "channel" concept
    on AutomationVersion beyond draft/published/deprecated/blocked — publishing
    an AutomationVersion is the closest real equivalent, see
    docs/certification-harness.md "Seed do Portal")

Running this twice must not create duplicate automations, versions, or
runtimes (docs/certification-harness.md item 38, "Idempotência do seed"):
categories/automations/runtimes are looked up by key/slug before creating,
and an AutomationVersion already in `published` status is left untouched
rather than re-uploaded.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from typing import Any

from tools.certification.api_client import PortalApiClient, PortalApiError
from tools.certification.manifests import (
    CERTIFICATION_CATEGORY_NAME,
    CERTIFICATION_CATEGORY_SLUG,
    CERTIFICATION_PACKAGES,
    CERTIFICATION_RUNTIME_ID,
    CERTIFICATION_RUNTIME_VERSION,
    CertificationPackageSpec,
    build_raw_manifest,
    package_source_dir,
)
from tools.certification.packaging import build_package_zip


@dataclass
class SeededPackage:
    package_id: str
    automation_id: int
    automation_version_id: int
    version: str
    status: str
    already_published: bool


def _ensure_runtime_published(client: PortalApiClient) -> dict[str, Any]:
    runtime = client.get_or_create_runtime(CERTIFICATION_RUNTIME_ID, "Python Core (certification)")
    runtime_version = client.get_or_create_runtime_version(runtime["id"], CERTIFICATION_RUNTIME_VERSION)
    if runtime_version.get("status") != "published":
        runtime_version = client.publish_runtime_version(runtime_version["id"])
    return runtime_version


def _ensure_package(
    client: PortalApiClient,
    spec: CertificationPackageSpec,
    version: dict[str, Any],
    certification_root: str,
    raw_manifest: str,
) -> None:
    source_dir = package_source_dir(spec, certification_root)
    built = build_package_zip(
        source_dir,
        f"{spec.package_id}-{spec.version}.zip",
        automation_yaml=raw_manifest,
        manifest_version=spec.version,
    )

    upload = client.initiate_package_upload(
        version["id"], built.file_name, built.size_bytes, built.sha256
    )
    with tempfile.TemporaryDirectory(prefix="certification_pkg_") as tmp:
        tmp_path = os.path.join(tmp, built.file_name)
        with open(tmp_path, "wb") as handle:
            handle.write(built.zip_bytes)
        client.upload_package_bytes(upload["id"], tmp_path, built.file_name)
    client.complete_package_upload(upload["id"])


def seed_certification(
    client: PortalApiClient, certification_root: str
) -> dict[str, SeededPackage]:
    category = client.get_or_create_category(
        CERTIFICATION_CATEGORY_NAME,
        CERTIFICATION_CATEGORY_SLUG,
        "Portal-Agent certification harness packages (docs/certification-harness.md).",
    )
    _ensure_runtime_published(client)

    results: dict[str, SeededPackage] = {}
    for spec in CERTIFICATION_PACKAGES:
        automation = client.get_or_create_automation(
            key=spec.package_id,
            name=spec.name,
            slug=spec.package_id.replace(".", "-"),
            category_id=category["id"],
            description=spec.description,
            timeout_seconds=spec.timeout_seconds,
        )
        existing_versions = client.list_automation_versions(automation["id"])
        active_spec = _select_seed_spec(spec, existing_versions)
        raw_manifest = build_raw_manifest(active_spec)
        version = _get_version_by_number(existing_versions, active_spec.version)
        if version is None:
            version = client.create_automation_version(
                automation["id"],
                raw_manifest,
                idempotency_key=f"certification-version-{automation['id']}-{active_spec.version}",
            )

        already_published = version.get("status") == "published"
        if not already_published:
            try:
                _ensure_package(client, active_spec, version, certification_root, raw_manifest)
            except PortalApiError as exc:
                # A previous partial run may have already attached a package
                # to this draft version; publish will fail loudly below if
                # that assumption is wrong, which is preferable to silently
                # swallowing a real provisioning error.
                if "package" not in str(exc.detail).lower():
                    raise
            version = client.publish_automation_version(version["id"])

        results[spec.package_id] = SeededPackage(
            package_id=spec.package_id,
            automation_id=automation["id"],
            automation_version_id=version["id"],
            version=version["version"],
            status=version["status"],
            already_published=already_published,
        )

    return results


def _get_version_by_number(versions: list[dict[str, Any]], version: str) -> dict[str, Any] | None:
    return next((item for item in versions if item.get("version") == version), None)


def _select_seed_spec(
    spec: CertificationPackageSpec,
    existing_versions: list[dict[str, Any]],
) -> CertificationPackageSpec:
    requested = _get_version_by_number(existing_versions, spec.version)
    if requested is None or requested.get("status") not in {"deprecated", "blocked"}:
        return spec

    major, minor, patch = _parse_semver(spec.version)
    while True:
        patch += 1
        candidate = f"{major}.{minor}.{patch}"
        existing = _get_version_by_number(existing_versions, candidate)
        if existing is None or existing.get("status") not in {"deprecated", "blocked"}:
            return replace(spec, version=candidate)


def _parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Certification package version must be semver-like: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])
