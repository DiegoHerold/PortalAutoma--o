from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from modules.catalog.domain.states import AutomationPackageStatus
from modules.catalog.domain.value_objects import ContentHash


@dataclass(frozen=True)
class PackageValidationIssue:
    code: str
    path: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PackageValidationResult:
    issues: tuple[PackageValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def to_payload(self) -> dict[str, Any]:
        return {
            "valid": self.is_valid,
            "issues": [
                {
                    "code": issue.code,
                    "path": issue.path,
                    "message": issue.message,
                    "details": issue.details,
                }
                for issue in self.issues
            ],
        }


@dataclass(frozen=True)
class AutomationPackage:
    id: str
    automation_version_id: str
    stored_object_id: str
    package_format: str
    file_name: str
    size_bytes: int
    sha256: str
    status: AutomationPackageStatus
    signature: str | None = None
    signature_algorithm: str | None = None
    signing_key_id: str | None = None
    validation_result: dict[str, Any] | None = None
    created_at: datetime | None = None
    validated_at: datetime | None = None
    published_at: datetime | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        ContentHash("sha256", self.sha256)
        if self.size_bytes <= 0:
            raise ValueError("Package size must be positive.")
        if self.package_format not in {"zip"}:
            raise ValueError("Only zip automation packages are supported.")

    @property
    def is_immutable(self) -> bool:
        return self.status in {
            AutomationPackageStatus.PUBLISHED,
            AutomationPackageStatus.BLOCKED,
        }
