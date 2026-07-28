from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from modules.telemetry.domain.value_objects import EventGap


@dataclass(frozen=True)
class EventAcknowledgement:
    execution_attempt_id: str
    highest_received_sequence: int
    highest_contiguous_sequence: int
    missing_ranges: list[EventGap] = field(default_factory=list)
    duplicate_sequences: list[int] = field(default_factory=list)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.highest_received_sequence < 0 or self.highest_contiguous_sequence < 0:
            raise ValueError("Acknowledgement sequences cannot be negative.")
        if self.highest_contiguous_sequence > self.highest_received_sequence:
            raise ValueError("Contiguous sequence cannot be greater than highest received.")

    def to_payload(self) -> dict:
        return {
            "execution_attempt_id": self.execution_attempt_id,
            "highest_received_sequence": self.highest_received_sequence,
            "highest_contiguous_sequence": self.highest_contiguous_sequence,
            "missing_ranges": [gap.to_payload() for gap in self.missing_ranges],
            "duplicate_sequences": self.duplicate_sequences,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
