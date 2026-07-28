from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from modules.dispatch.domain.states import ExecutionLeaseStatus


@dataclass(frozen=True)
class ExecutionLease:
    id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    status: ExecutionLeaseStatus
    issued_at: datetime
    expires_at: datetime
    last_renewed_at: datetime | None
    renewal_sequence: int
    grace_until: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    @classmethod
    def issue(
        cls,
        *,
        id: str,
        execution_attempt_id: str,
        agent_id: str,
        agent_instance_id: str,
        issued_at: datetime,
        expires_at: datetime,
        grace_until: datetime,
    ) -> "ExecutionLease":
        if expires_at <= issued_at:
            raise ValueError("ExecutionLease expiration must be after issued_at.")
        if grace_until < expires_at:
            raise ValueError("ExecutionLease grace_until must not be before expires_at.")
        return cls(
            id=id,
            execution_attempt_id=execution_attempt_id,
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            status=ExecutionLeaseStatus.ACTIVE,
            issued_at=issued_at,
            expires_at=expires_at,
            last_renewed_at=issued_at,
            renewal_sequence=0,
            grace_until=grace_until,
        )

    def renew(self, *, renewal_sequence: int, now: datetime, expires_at: datetime, grace_until: datetime) -> "ExecutionLease":
        if self.status != ExecutionLeaseStatus.ACTIVE:
            return self
        if renewal_sequence < self.renewal_sequence:
            raise ValueError("Lease renewal sequence went backwards.")
        if renewal_sequence == self.renewal_sequence:
            return self
        return replace(
            self,
            renewal_sequence=renewal_sequence,
            last_renewed_at=now,
            expires_at=expires_at,
            grace_until=grace_until,
        )

    def mark_suspect(self) -> "ExecutionLease":
        if self.status != ExecutionLeaseStatus.ACTIVE:
            return self
        return replace(self, status=ExecutionLeaseStatus.SUSPECT)

    def expire(self) -> "ExecutionLease":
        if self.status == ExecutionLeaseStatus.EXPIRED:
            return self
        return replace(self, status=ExecutionLeaseStatus.EXPIRED)

    def revoke(self, now: datetime, reason: str | None = None) -> "ExecutionLease":
        if self.status == ExecutionLeaseStatus.REVOKED:
            return self
        return replace(self, status=ExecutionLeaseStatus.REVOKED, revoked_at=now, revocation_reason=reason)

    def complete(self, now: datetime) -> "ExecutionLease":
        if self.status == ExecutionLeaseStatus.COMPLETED:
            return self
        return replace(self, status=ExecutionLeaseStatus.COMPLETED, revoked_at=now, revocation_reason="completed")
