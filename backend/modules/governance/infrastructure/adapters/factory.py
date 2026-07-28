from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.access.infrastructure.repositories import SqlAlchemyTransactionManager
from modules.governance.infrastructure.encryption import LocalFernetSecretCipher
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository, SqlAlchemyGovernanceRepository


@dataclass
class GovernanceAdapters:
    audit: SqlAlchemyAuditEventRepository
    governance: SqlAlchemyGovernanceRepository
    cipher: LocalFernetSecretCipher
    transaction: SqlAlchemyTransactionManager


def build_governance_adapters(db: Session) -> GovernanceAdapters:
    return GovernanceAdapters(
        audit=SqlAlchemyAuditEventRepository(db),
        governance=SqlAlchemyGovernanceRepository(db),
        cipher=LocalFernetSecretCipher(),
        transaction=SqlAlchemyTransactionManager(db),
    )
