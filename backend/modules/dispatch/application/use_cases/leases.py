from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from modules.dispatch.application.ports import ExecutionLeaseRepository, OutboxPort, TransactionManager


class ReconcileExpiredLeases:
    def __init__(self, leases: ExecutionLeaseRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, *, limit: int = 100) -> dict[str, int]:
        now = datetime.now(UTC)
        suspect = 0
        expired = 0
        for lease in self.leases.due_for_suspect(now, limit=limit):
            saved = self.leases.save(replace(lease, status="suspect"))
            self.outbox.append_event("execution_lease.suspect", "execution_attempt", saved.execution_attempt_id, {"execution_attempt_id": saved.execution_attempt_id, "lease_id": saved.id})
            suspect += 1
        for lease in self.leases.due_for_expiration(now, limit=limit):
            saved = self.leases.save(replace(lease, status="expired"))
            self.outbox.append_event("execution_lease.expired", "execution_attempt", saved.execution_attempt_id, {"execution_attempt_id": saved.execution_attempt_id, "lease_id": saved.id})
            expired += 1
        self.transaction.commit()
        return {"suspect": suspect, "expired": expired}


class RevokeExecutionLease:
    def __init__(self, leases: ExecutionLeaseRepository, outbox: OutboxPort, transaction: TransactionManager) -> None:
        self.leases = leases
        self.outbox = outbox
        self.transaction = transaction

    def execute(self, lease_id: str, reason: str) -> dict[str, str]:
        now = datetime.now(UTC)
        lease = self.leases.get(lease_id)
        if lease is None:
            raise ValueError("ExecutionLease not found.")
        saved = self.leases.save(replace(lease, status="revoked", revoked_at=now, revocation_reason=reason))
        self.outbox.append_event("execution_lease.revoked", "execution_attempt", saved.execution_attempt_id, {"execution_attempt_id": saved.execution_attempt_id, "lease_id": saved.id, "reason": reason})
        self.transaction.commit()
        return {"lease_id": saved.id, "status": saved.status}
