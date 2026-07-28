from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventGap:
    start_sequence: int
    end_sequence: int

    def __post_init__(self) -> None:
        if self.start_sequence <= 0 or self.end_sequence < self.start_sequence:
            raise ValueError("EventGap requires a positive inclusive sequence range.")

    def to_payload(self) -> dict[str, int]:
        return {"from": self.start_sequence, "to": self.end_sequence}
