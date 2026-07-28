from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.access.infrastructure.authentication import JwtTokenIssuer
from modules.access.infrastructure.hashing import PasslibPasswordHasher
from modules.access.infrastructure.repositories import SqlAlchemyAccessRepository, SqlAlchemyTransactionManager
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository


@dataclass
class AccessAdapters:
    access: SqlAlchemyAccessRepository
    passwords: PasslibPasswordHasher
    tokens: JwtTokenIssuer
    audit: SqlAlchemyAuditEventRepository
    transaction: SqlAlchemyTransactionManager


def build_access_adapters(db: Session) -> AccessAdapters:
    return AccessAdapters(
        access=SqlAlchemyAccessRepository(db),
        passwords=PasslibPasswordHasher(),
        tokens=JwtTokenIssuer(),
        audit=SqlAlchemyAuditEventRepository(db),
        transaction=SqlAlchemyTransactionManager(db),
    )

