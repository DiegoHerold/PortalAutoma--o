from __future__ import annotations

from enum import StrEnum


class AutomationVersionStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class ManifestValidationStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"


class AutomationPackageStatus(StrEnum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class RuntimeStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class RuntimeVersionStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class RuntimeArtifactStatus(StrEnum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    PUBLISHED = "published"
    BLOCKED = "blocked"


ALLOWED_AUTOMATION_VERSION_TRANSITIONS: dict[AutomationVersionStatus, set[AutomationVersionStatus]] = {
    AutomationVersionStatus.DRAFT: {AutomationVersionStatus.VALIDATING},
    AutomationVersionStatus.VALIDATING: {
        AutomationVersionStatus.DRAFT,
        AutomationVersionStatus.PUBLISHED,
        AutomationVersionStatus.BLOCKED,
    },
    AutomationVersionStatus.PUBLISHED: {
        AutomationVersionStatus.DEPRECATED,
        AutomationVersionStatus.BLOCKED,
    },
    AutomationVersionStatus.DEPRECATED: {AutomationVersionStatus.BLOCKED},
    AutomationVersionStatus.BLOCKED: set(),
}


ALLOWED_RUNTIME_VERSION_TRANSITIONS: dict[RuntimeVersionStatus, set[RuntimeVersionStatus]] = {
    RuntimeVersionStatus.DRAFT: {RuntimeVersionStatus.VALIDATING},
    RuntimeVersionStatus.VALIDATING: {
        RuntimeVersionStatus.PUBLISHED,
        RuntimeVersionStatus.BLOCKED,
        RuntimeVersionStatus.DRAFT,
    },
    RuntimeVersionStatus.PUBLISHED: {
        RuntimeVersionStatus.DEPRECATED,
        RuntimeVersionStatus.BLOCKED,
    },
    RuntimeVersionStatus.DEPRECATED: {RuntimeVersionStatus.BLOCKED},
    RuntimeVersionStatus.BLOCKED: set(),
}
