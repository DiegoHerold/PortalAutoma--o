from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InvalidStateTransition(ValueError):
    pass


@dataclass(frozen=True)
class StateMachine:
    name: str
    transitions: dict[StrEnum, set[StrEnum]]

    def can_transition(self, current: StrEnum, target: StrEnum) -> bool:
        return target in self.transitions.get(current, set())

    def ensure_transition(self, current: StrEnum, target: StrEnum) -> None:
        if not self.can_transition(current, target):
            raise InvalidStateTransition(f"{self.name}: cannot transition from {current} to {target}")

