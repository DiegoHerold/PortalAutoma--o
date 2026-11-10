from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from modules.catalog.domain.errors import InvalidCatalogStateTransition
from modules.catalog.domain.states import (
    ALLOWED_RUNTIME_VERSION_TRANSITIONS,
    RuntimeArtifactStatus,
    RuntimeStatus,
    RuntimeVersionStatus,
)
from modules.catalog.domain.value_objects import SemVer


@dataclass(frozen=True)
class Runtime:
    id: str
    key: str
    name: str
    description: str | None = None
    status: RuntimeStatus = RuntimeStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("Runtime key is required.")
        if not self.name:
            raise ValueError("Runtime name is required.")


@dataclass(frozen=True)
class RuntimeVersion:
    id: str
    runtime_id: str
    version: str
    operating_system: str
    architecture: str
    status: RuntimeVersionStatus = RuntimeVersionStatus.DRAFT
    minimum_agent_version: str | None = None
    supported_entrypoints: tuple[str, ...] = ()
    supported_execution_modes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    published_at: datetime | None = None
    deprecated_at: datetime | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        SemVer(self.version)
        if not self.operating_system:
            raise ValueError("RuntimeVersion operating_system is required.")
        if not self.architecture:
            raise ValueError("RuntimeVersion architecture is required.")

    def transition_to(self, status: RuntimeVersionStatus) -> "RuntimeVersion":
        if status not in ALLOWED_RUNTIME_VERSION_TRANSITIONS[self.status]:
            raise InvalidCatalogStateTransition(f"Cannot transition runtime version from {self.status} to {status}.")
        now = datetime.now(UTC)
        return RuntimeVersion(
            id=self.id,
            runtime_id=self.runtime_id,
            version=self.version,
            operating_system=self.operating_system,
            architecture=self.architecture,
            status=status,
            minimum_agent_version=self.minimum_agent_version,
            supported_entrypoints=self.supported_entrypoints,
            supported_execution_modes=self.supported_execution_modes,
            metadata=self.metadata,
            created_at=self.created_at,
            published_at=now if status == RuntimeVersionStatus.PUBLISHED else self.published_at,
            deprecated_at=now if status == RuntimeVersionStatus.DEPRECATED else self.deprecated_at,
            blocked_at=now if status == RuntimeVersionStatus.BLOCKED else self.blocked_at,
        )


@dataclass(frozen=True)
class RuntimeArtifact:
    id: str
    runtime_version_id: str
    stored_object_id: str
    file_name: str
    size_bytes: int
    sha256: str
    status: RuntimeArtifactStatus
    signature: str | None = None
    signature_algorithm: str | None = None
    signing_key_id: str | None = None
    created_at: datetime | None = None
    validated_at: datetime | None = None
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("Runtime artifact size must be positive.")
