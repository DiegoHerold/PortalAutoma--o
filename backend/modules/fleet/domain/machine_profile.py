from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AgentMachineProfile:
    id: str
    agent_id: str
    agent_instance_id: str
    hostname: str
    observed_at: datetime
    operating_system: str | None = None
    operating_system_version: str | None = None
    operating_system_build: str | None = None
    architecture: str | None = None
    cpu_model: str | None = None
    physical_cores: int | None = None
    logical_processors: int | None = None
    total_memory_mb: int | None = None
    disk_volumes: list[dict[str, Any]] = field(default_factory=list)
    network_summary: dict[str, Any] = field(default_factory=dict)
    interactive_session_supported: bool | None = None
    revision: int = 1
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.hostname:
            raise ValueError("Machine profile hostname is required.")
        if self.revision < 1:
            raise ValueError("Machine profile revision must be positive.")
