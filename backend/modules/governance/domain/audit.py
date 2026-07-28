from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    id: str
    actor_type: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    organization_id: int | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("Audit action is required.")
        if not self.resource_type or not self.resource_id:
            raise ValueError("Audit resource identity is required.")
