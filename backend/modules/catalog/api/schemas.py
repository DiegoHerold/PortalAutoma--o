from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class CategoryUpdateRequest(CategoryCreateRequest):
    pass


class CategoryResponse(CategoryCreateRequest):
    id: int


class AutomationCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    category_id: int = Field(gt=0)
    executor_type: str = Field(min_length=1)
    package_url: str | None = None
    package_sha256: str | None = None
    default_priority: str = "normal"
    timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=0, ge=0)
    is_active: bool = True


class AutomationUpdateRequest(AutomationCreateRequest):
    pass


class AutomationResponse(AutomationCreateRequest):
    id: int


class AutomationSourceResponse(BaseModel):
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


class WorkerPreferenceItem(BaseModel):
    worker_id: int = Field(gt=0)
    priority_order: int = Field(ge=0)


class WorkerPreferenceUpdateRequest(BaseModel):
    preferences: list[WorkerPreferenceItem] = Field(default_factory=list)


class WorkerPreferenceResponse(BaseModel):
    worker_id: int
    worker_name: str
    priority_order: int
    is_active: bool


class AutomationSyncResponse(BaseModel):
    update_available: bool
    current_commit: str | None = None
    latest_commit: str | None = None
    current_version: str | None = None


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


class AutomationImportPreview(BaseModel):
    staging_id: str | None = None
    key: str | None = None
    name: str | None = None
    version: str | None = None
    description: str | None = None
    category: str | None = None
    runtime_id: str | None = None
    entrypoint_type: str | None = None
    path: str | None = None
    manifest_path: str | None = None
    commit_sha: str | None = None
    source_type: str
    already_imported: bool
    validation_status: str
    errors: list[str] = Field(default_factory=list)
    package_sha256: str
    package_size: int


class AutomationImportConfirmRequest(BaseModel):
    category_id: int | None = None


class GithubIntegrationResponse(BaseModel):
    id: int
    installation_id: int
    account_login: str
    account_type: str
    connected_at: datetime | None = None
    suspended_at: datetime | None = None


class GithubConnectResponse(BaseModel):
    install_url: str


class GithubRepositoryResponse(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool


class GithubDiscoverRequest(BaseModel):
    owner: str
    repository: str
    branch: str


class GithubImportRequest(BaseModel):
    owner: str
    repository: str
    branch: str
    manifest_paths: list[str]
