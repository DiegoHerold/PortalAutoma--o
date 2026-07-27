from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryEnvelope:
    actor_id: str | None = None
