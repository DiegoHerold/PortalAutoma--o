from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class AutomationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Automation:
    id: str
    key: str
    name: str
    description: str | None
    category: str | None
    tags: tuple[str, ...] = ()
    status: AutomationStatus = AutomationStatus.ACTIVE
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("Automation key is required.")
        if not self.name or not self.name.strip():
            raise ValueError("Automation name is required.")
        if self.status == AutomationStatus.ARCHIVED and self.id == "":
            raise ValueError("Archived automations must have an identity.")

    def rename(self, name: str, description: str | None, category: str | None, tags: tuple[str, ...]) -> "Automation":
        return Automation(
            id=self.id,
            key=self.key,
            name=name,
            description=description,
            category=category,
            tags=tags,
            status=self.status,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )

    def archive(self) -> "Automation":
        return Automation(
            id=self.id,
            key=self.key,
            name=self.name,
            description=self.description,
            category=self.category,
            tags=self.tags,
            status=AutomationStatus.ARCHIVED,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )
