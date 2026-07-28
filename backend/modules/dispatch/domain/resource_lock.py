from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from modules.dispatch.domain.states import ResourceLockStatus


@dataclass(frozen=True)
class ResourceLock:
    id: str
    resource_key: str
    scope: str
    agent_id: str
    execution_attempt_id: str
    status: ResourceLockStatus
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None
    release_reason: str | None = None

    @property
    def normalized_key(self) -> str:
        return normalize_resource_key(self.resource_key)

    @classmethod
    def acquire(
        cls,
        *,
        id: str,
        resource_key: str,
        scope: str,
        agent_id: str,
        execution_attempt_id: str,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> "ResourceLock":
        if expires_at <= acquired_at:
            raise ValueError("ResourceLock expiration must be after acquired_at.")
        return cls(
            id=id,
            resource_key=resource_key,
            scope=scope or "global",
            agent_id=agent_id,
            execution_attempt_id=execution_attempt_id,
            status=ResourceLockStatus.ACTIVE,
            acquired_at=acquired_at,
            expires_at=expires_at,
        )

    def renew(self, expires_at: datetime) -> "ResourceLock":
        if self.status != ResourceLockStatus.ACTIVE:
            return self
        if expires_at <= self.expires_at:
            return self
        return replace(self, expires_at=expires_at)

    def release(self, now: datetime, reason: str | None = None) -> "ResourceLock":
        if self.status == ResourceLockStatus.RELEASED:
            return self
        return replace(self, status=ResourceLockStatus.RELEASED, released_at=now, release_reason=reason)

    def expire(self, now: datetime) -> "ResourceLock":
        if self.status == ResourceLockStatus.EXPIRED:
            return self
        return replace(self, status=ResourceLockStatus.EXPIRED, released_at=now, release_reason="expired")

    def revoke(self, now: datetime, reason: str | None = None) -> "ResourceLock":
        if self.status == ResourceLockStatus.REVOKED:
            return self
        return replace(self, status=ResourceLockStatus.REVOKED, released_at=now, release_reason=reason)


def normalize_resource_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("\\", "/").split())
