from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modules.dispatch.application.use_cases.job_tokens import StoredJobToken
from modules.dispatch.infrastructure.orm.models import DirectCommandRecord, JobTokenRecord
from modules.fleet.infrastructure.orm.models import DirectInstanceRecord


class SqlAlchemyJobTokenStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, *, token_id: str, task_execution_id: str, execution_attempt_id: str, direct_instance_id: str,
            token_hash: str, expires_at: datetime) -> None:
        self.db.add(JobTokenRecord(id=token_id, task_execution_id=task_execution_id,
                                   execution_attempt_id=execution_attempt_id, direct_instance_id=direct_instance_id,
                                   token_hash=token_hash, expires_at=expires_at))
        self.db.flush()

    def find(self, token_hash: str) -> StoredJobToken | None:
        linha = self.db.execute(
            select(JobTokenRecord, DirectInstanceRecord.status)
            .join(DirectInstanceRecord, DirectInstanceRecord.id == JobTokenRecord.direct_instance_id)
            .where(JobTokenRecord.token_hash == token_hash)
        ).one_or_none()
        if linha is None:
            return None
        token, status = linha
        return StoredJobToken(token.task_execution_id, token.execution_attempt_id, token.direct_instance_id,
                              token.expires_at, token.revoked_at, status)

    def touch_instance(self, instance_id: str, now: datetime) -> None:
        """Último sinal da instância direta: usado pela fila (máquina com sinal) e pelo job perdido."""
        self.db.execute(update(DirectInstanceRecord).where(DirectInstanceRecord.id == instance_id).values(last_seen_at=now))


class SqlAlchemyDirectCommandStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, *, command_id: str, execution_attempt_id: str, command: dict[str, Any]) -> None:
        self.db.add(DirectCommandRecord(id=command_id, execution_attempt_id=execution_attempt_id, command=command))
        self.db.flush()

    def take_pending(self, execution_attempt_id: str, now: datetime) -> list[dict[str, Any]]:
        linhas = list(self.db.scalars(
            select(DirectCommandRecord)
            .where(DirectCommandRecord.execution_attempt_id == execution_attempt_id, DirectCommandRecord.status == "pendente")
            .order_by(DirectCommandRecord.created_at).with_for_update(skip_locked=True)
        ))
        if linhas:
            self.db.execute(update(DirectCommandRecord).where(DirectCommandRecord.id.in_([l.id for l in linhas]))
                            .values(status="entregue", delivered_at=now))
        return [dict(l.command) for l in linhas]


class SqlAlchemyDirectDeliveryReader:
    """O job reservado para uma instância direta e ainda não começado (sem nenhum evento)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def tentativa_pendente(self, instancia_id: str) -> dict[str, Any] | None:
        from modules.orchestration.infrastructure.orm.models import (
            ExecutionAttemptRecord,
            ExecutionItemRecord,
            TaskExecutionRecord,
        )
        from modules.telemetry.infrastructure.orm.models import ExecutionEventRecord

        sem_evento = ~select(ExecutionEventRecord.id).where(
            ExecutionEventRecord.execution_attempt_id == ExecutionAttemptRecord.id).exists()
        linha = self.db.execute(
            select(ExecutionAttemptRecord, TaskExecutionRecord)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .where(ExecutionAttemptRecord.executor_type == "direct", ExecutionAttemptRecord.executor_id == instancia_id,
                   ExecutionAttemptRecord.status == "committed", TaskExecutionRecord.status == "running", sem_evento)
            .order_by(ExecutionAttemptRecord.created_at).limit(1)
        ).first()
        if linha is None:
            return None
        tentativa, tarefa = linha
        itens = self.db.execute(
            select(ExecutionItemRecord.item_key, ExecutionItemRecord.label)
            .where(ExecutionItemRecord.task_execution_id == tarefa.id).order_by(ExecutionItemRecord.item_key)
        ).all()
        da_entrada = {str(i.get("chave")): i for i in ((tarefa.input or {}).get("itens") or []) if isinstance(i, dict)}
        return {
            "attempt_id": tentativa.id, "attempt_number": tentativa.attempt_number, "job_id": tarefa.id,
            "execution_id": tarefa.execution_id, "parametros": dict(tarefa.parameters or {}),
            "itens": [{"chave": k, "rotulo": r, "grupo": (da_entrada.get(k) or {}).get("grupo"),
                       "configuracao": (da_entrada.get(k) or {}).get("configuracao") or {}} for k, r in itens]
            or list(da_entrada.values()),
        }

    def revogar_tokens(self, attempt_id: str, agora: datetime) -> None:
        self.db.execute(update(JobTokenRecord).where(JobTokenRecord.execution_attempt_id == attempt_id,
                                                    JobTokenRecord.revoked_at.is_(None)).values(revoked_at=agora))
