from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortalContext:
    name: str
    responsibilities: tuple[str, ...]
    owns: tuple[str, ...]
