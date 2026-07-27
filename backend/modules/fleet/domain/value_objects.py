from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime


def utcnow() -> datetime:
    return datetime.utcnow()


def generate_agent_id() -> str:
    return f"agt_{secrets.token_urlsafe(18).replace('-', '').replace('_', '')[:24]}"


def generate_agent_instance_id() -> str:
    return f"agi_{secrets.token_urlsafe(18).replace('-', '').replace('_', '')[:24]}"


def generate_registration_token() -> str:
    return f"reg_{secrets.token_urlsafe(32)}"


def generate_agent_secret() -> str:
    return f"ac_{secrets.token_urlsafe(40)}"


def hash_secret(secret: str, pepper: str = "") -> str:
    payload = f"{pepper}:{secret}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def secrets_match(secret: str, expected_hash: str, pepper: str = "") -> bool:
    return hmac.compare_digest(hash_secret(secret, pepper), expected_hash)


@dataclass(frozen=True)
class AgentIdentity:
    local_identity: str
    hostname: str
    machine_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.local_identity:
            raise ValueError("Agent local identity is required.")
        if not self.hostname:
            raise ValueError("Agent hostname is required.")


@dataclass(frozen=True)
class ProtocolSelection:
    selected_protocol_version: str
    heartbeat_interval_seconds: int
    stale_after_seconds: int
    offline_after_seconds: int
