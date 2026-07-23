from datetime import datetime

from pydantic import BaseModel


class AutomationImportPreview(BaseModel):
    """One discovered/uploaded automation, awaiting user confirmation."""

    staging_id: str
    key: str
    name: str
    version: str
    description: str | None = None
    category: str | None = None
    runtime_id: str
    entrypoint_type: str
    path: str | None = None
    manifest_path: str | None = None
    commit_sha: str | None = None
    source_type: str  # "github" | "manual_upload"
    already_imported: bool
    validation_status: str  # "valid" | "invalid"
    errors: list[str] = []
    package_sha256: str
    package_size: int


class AutomationImportConfirmRequest(BaseModel):
    category_id: int | None = None


class AutomationVersionRead(BaseModel):
    id: int
    automation_id: int
    version: str
    status: str
    runtime_id: str
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

    class Config:
        from_attributes = True


class AutomationSourceRead(BaseModel):
    id: int
    automation_id: int
    type: str
    owner: str | None
    repository: str | None
    branch: str | None
    automation_path: str | None
    manifest_path: str | None
    last_commit_sha: str | None
    last_synced_at: datetime | None
    sync_status: str | None
    original_filename: str | None
    uploaded_at: datetime | None

    class Config:
        from_attributes = True
