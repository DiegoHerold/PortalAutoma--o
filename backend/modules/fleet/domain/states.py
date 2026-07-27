from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.fleet.domain.agent import (
    AgentAdministrativeStatus,
    AgentConnectivityStatus,
    AgentHealthStatus,
    AgentOccupancyStatus,
)


REGISTRATION_TOKEN_ACTIVE = "active"
REGISTRATION_TOKEN_USED = "used"
REGISTRATION_TOKEN_EXPIRED = "expired"
REGISTRATION_TOKEN_REVOKED = "revoked"

CREDENTIAL_ACTIVE = "active"
CREDENTIAL_EXPIRED = "expired"
CREDENTIAL_ROTATED = "rotated"
CREDENTIAL_REVOKED = "revoked"

INTERACTIVE_UNAVAILABLE = "unavailable"
INTERACTIVE_AVAILABLE_LOCKED = "available_locked"
INTERACTIVE_AVAILABLE_UNLOCKED = "available_unlocked"
INTERACTIVE_UNKNOWN = "unknown"

POOL_INTERACTIVE = "interactive"
POOL_BACKGROUND = "background"
POOL_BROWSER = "browser"
DEFAULT_AGENT_POOLS = (POOL_INTERACTIVE, POOL_BACKGROUND, POOL_BROWSER)


@dataclass(frozen=True)
class PresencePolicy:
    heartbeat_interval_seconds: int = 30
    stale_after_seconds: int = 90
    offline_after_seconds: int = 180

    def connectivity_for(self, last_seen_at: datetime | None, now: datetime) -> AgentConnectivityStatus:
        if last_seen_at is None:
            return AgentConnectivityStatus.OFFLINE
        age_seconds = (now - last_seen_at).total_seconds()
        if age_seconds >= self.offline_after_seconds:
            return AgentConnectivityStatus.OFFLINE
        if age_seconds >= self.stale_after_seconds:
            return AgentConnectivityStatus.STALE
        return AgentConnectivityStatus.ONLINE


__all__ = [
    "AgentAdministrativeStatus",
    "AgentConnectivityStatus",
    "AgentHealthStatus",
    "AgentOccupancyStatus",
    "CREDENTIAL_ACTIVE",
    "CREDENTIAL_EXPIRED",
    "CREDENTIAL_REVOKED",
    "CREDENTIAL_ROTATED",
    "DEFAULT_AGENT_POOLS",
    "INTERACTIVE_AVAILABLE_LOCKED",
    "INTERACTIVE_AVAILABLE_UNLOCKED",
    "INTERACTIVE_UNAVAILABLE",
    "INTERACTIVE_UNKNOWN",
    "POOL_BACKGROUND",
    "POOL_BROWSER",
    "POOL_INTERACTIVE",
    "PresencePolicy",
    "REGISTRATION_TOKEN_ACTIVE",
    "REGISTRATION_TOKEN_EXPIRED",
    "REGISTRATION_TOKEN_REVOKED",
    "REGISTRATION_TOKEN_USED",
]
