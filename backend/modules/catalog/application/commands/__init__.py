from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandEnvelope:
    payload: dict[str, Any]
    actor_id: str | None = None
    idempotency_key: str | None = None
