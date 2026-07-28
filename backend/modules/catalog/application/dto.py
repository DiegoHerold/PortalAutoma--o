from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ActorDTO:
    actor_type: str
    actor_id: str | None
    actor_email: str | None = None


@dataclass(frozen=True)
class CategoryDTO:
    id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class AutomationDTO:
    id: int
    key: str | None
    name: str
    slug: str
    description: str | None
    category_id: int
    executor_type: str
    package_url: str | None
    package_sha256: str | None
    default_priority: str
    timeout_seconds: int
    max_retries: int
    is_active: bool
    status: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class AutomationSourceDTO:
    id: int
    automation_id: int
    type: str
    integration_id: int | None = None
    owner: str | None = None
    repository: str | None = None
    branch: str | None = None
    automation_path: str | None = None
    manifest_path: str | None = None
    last_commit_sha: str | None = None
    last_synced_at: datetime | None = None
    sync_status: str | None = None
    original_filename: str | None = None
    uploaded_at: datetime | None = None


@dataclass(frozen=True)
class AutomationVersionDTO:
    id: int
    automation_id: int
    version: str
    status: str
    runtime_id: str
    runtime_version: str | None
    entrypoint_type: str
    application_type: str
    artifact_bucket: str
    artifact_object_key: str
    artifact_size: int
    artifact_sha256: str
    source_commit_sha: str | None
    source_path: str | None
    created_at: datetime
    published_at: datetime | None
    manifest_id: str | None = None
    package_id: str | None = None
    runtime_version_id: str | None = None
    validation_errors: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class RuntimeDTO:
    id: str
    key: str
    name: str
    description: str | None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RuntimeVersionDTO:
    id: str
    runtime_id: str
    version: str
    operating_system: str
    architecture: str
    status: str
    minimum_agent_version: str | None
    supported_entrypoints: list[str]
    supported_execution_modes: list[str]
    metadata: dict[str, Any]
    created_at: datetime | None = None
    published_at: datetime | None = None
    deprecated_at: datetime | None = None
    blocked_at: datetime | None = None


@dataclass(frozen=True)
class PackageDTO:
    id: str
    automation_version_id: int
    stored_object_id: str
    package_format: str
    file_name: str
    size_bytes: int
    sha256: str
    status: str
    validation_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class PackageUploadDTO:
    id: str
    stored_object_id: str
    package_id: str
    upload_url: str | None
    expires_at: datetime | None
