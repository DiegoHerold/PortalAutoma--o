from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuntimeCreateRequest(BaseModel):
    key: str
    name: str
    description: str | None = None


class RuntimeResponse(RuntimeCreateRequest):
    id: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RuntimeVersionCreateRequest(BaseModel):
    version: str
    operating_system: str = "windows"
    architecture: str = "x64"
    minimum_agent_version: str | None = None
    supported_entrypoints: list[str] = Field(default_factory=lambda: ["python-function"])
    supported_execution_modes: list[str] = Field(default_factory=lambda: ["interactive", "background"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeVersionResponse(RuntimeVersionCreateRequest):
    id: str
    runtime_id: str
    status: str
    created_at: datetime | None = None
    published_at: datetime | None = None
    deprecated_at: datetime | None = None
    blocked_at: datetime | None = None


class AutomationVersionCreateRequest(BaseModel):
    raw_manifest: str
    release_notes: str | None = None
    source_repository: str | None = None
    source_branch: str | None = None
    source_tag: str | None = None
    source_commit_sha: str | None = None
    build_id: str | None = None


class AutomationVersionResponse(BaseModel):
    id: int
    automation_id: int
    version: str
    status: str
    runtime_id: str
    runtime_version: str | None = None
    entrypoint_type: str
    application_type: str
    artifact_bucket: str
    artifact_object_key: str
    artifact_size: int
    artifact_sha256: str
    source_commit_sha: str | None = None
    source_path: str | None = None
    created_at: datetime
    published_at: datetime | None = None
    manifest_id: str | None = None
    package_id: str | None = None
    runtime_version_id: str | None = None
    validation_errors: list[dict[str, Any]] | None = None


class PackageUploadCreateRequest(BaseModel):
    file_name: str
    expected_size_bytes: int | None = None
    expected_sha256: str | None = None


class PackageUploadResponse(BaseModel):
    id: str
    stored_object_id: str
    package_id: str
    upload_url: str | None
    expires_at: datetime | None = None


class PackageResponse(BaseModel):
    id: str
    automation_version_id: int
    stored_object_id: str
    package_format: str
    file_name: str
    size_bytes: int
    sha256: str
    status: str
    validation_result: dict[str, Any] | None = None


class BlockRequest(BaseModel):
    reason: str | None = None
