from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentDiagnostic:
    id: str
    agent_id: str
    agent_instance_id: str | None
    request_command_id: str | None
    status: str
    requested_at: datetime
    summary: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifact_id: str | None = None
    completed_at: datetime | None = None
    error: str | None = None
