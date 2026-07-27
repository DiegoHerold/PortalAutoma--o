from __future__ import annotations

from typing import Protocol

from modules.governance.domain.audit import AuditEvent


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent:
        raise NotImplementedError
