"""Token do job no modo direto (ADR-018): só vale para aquele job e vence.

O token em texto aparece uma única vez, na emissão; o Portal guarda só o hash.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

DURACAO_PADRAO = timedelta(hours=12)


class JobTokenRejected(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class JobTokenGrant:
    task_execution_id: str
    execution_attempt_id: str
    direct_instance_id: str
    instance_status: str


@dataclass(frozen=True)
class StoredJobToken:
    task_execution_id: str
    execution_attempt_id: str
    direct_instance_id: str
    expires_at: datetime
    revoked_at: datetime | None
    instance_status: str


class JobTokenStore(Protocol):
    def add(self, *, token_id: str, task_execution_id: str, execution_attempt_id: str, direct_instance_id: str,
            token_hash: str, expires_at: datetime) -> None: ...

    def find(self, token_hash: str) -> StoredJobToken | None: ...


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class IssueJobToken:
    def __init__(self, store: JobTokenStore) -> None:
        self.store = store

    def execute(self, *, task_execution_id: str, execution_attempt_id: str, direct_instance_id: str, now: datetime,
                duracao: timedelta = DURACAO_PADRAO) -> str:
        token = f"jbt_{secrets.token_urlsafe(32)}"
        self.store.add(token_id=f"jtk_{uuid4().hex}", task_execution_id=task_execution_id,
                       execution_attempt_id=execution_attempt_id, direct_instance_id=direct_instance_id,
                       token_hash=hash_do_token(token), expires_at=now + duracao)
        return token


class AuthenticateJobToken:
    def __init__(self, store: JobTokenStore) -> None:
        self.store = store

    def execute(self, *, job_id: str, token: str | None, now: datetime) -> JobTokenGrant:
        if not token:
            raise JobTokenRejected("token_ausente")
        guardado = self.store.find(hash_do_token(token))
        if guardado is None:
            raise JobTokenRejected("token_invalido")
        if guardado.task_execution_id != job_id:
            raise JobTokenRejected("token_de_outro_job")
        if guardado.revoked_at is not None:
            raise JobTokenRejected("token_revogado")
        if guardado.expires_at <= now:
            raise JobTokenRejected("token_vencido")
        if guardado.instance_status == "revogada":
            raise JobTokenRejected("instancia_revogada")
        if guardado.instance_status not in ("aprovada", "quarentena"):
            raise JobTokenRejected("instancia_nao_aprovada")
        # Quarentena: a instância conecta e termina o job atual, mas não recebe jobs novos (Fase 3).
        return JobTokenGrant(guardado.task_execution_id, guardado.execution_attempt_id,
                             guardado.direct_instance_id, guardado.instance_status)
