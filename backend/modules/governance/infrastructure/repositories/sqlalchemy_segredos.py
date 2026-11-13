"""Segredos ligados às automações (13/11/2026): consultas e gravações do Governance.

A ligação é uma concessão ``grantee_type="automation"``, ``permission="use"``. Os nomes das
automações são só leitura (modelo de leitura), como no Painel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from modules.governance.infrastructure.orm.models import SecretGrantRecord, SecretRecord, SecretVersionRecord

TIPO = "automation"
USO = "use"


class SqlAlchemySegredos:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- leitura -----------------------------------------------------------------------
    def segredo(self, segredo_id: str) -> SecretRecord | None:
        return self.db.get(SecretRecord, segredo_id)

    def versao_atual(self, segredo: SecretRecord) -> SecretVersionRecord | None:
        return self.db.get(SecretVersionRecord, segredo.current_version_id) if segredo.current_version_id else None

    def versoes(self, segredo_id: str) -> list[SecretVersionRecord]:
        return list(self.db.scalars(select(SecretVersionRecord).where(SecretVersionRecord.secret_id == segredo_id)
                                    .order_by(SecretVersionRecord.version.desc())).all())

    def todos(self) -> list[SecretRecord]:
        return list(self.db.scalars(select(SecretRecord).order_by(SecretRecord.name)).all())

    def automacao_existe(self, automation_id: int) -> bool:
        return self.db.execute(text("SELECT 1 FROM automations WHERE id = :a"), {"a": automation_id}).first() is not None

    def nomes_das_automacoes(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        linhas = self.db.execute(text("SELECT id, name FROM automations WHERE id = ANY(:ids)"), {"ids": list(ids)}).all()
        return {int(i): n for i, n in linhas}

    def ligacoes(self, *, segredo_id: str | None = None, automation_id: int | None = None,
                 agora: datetime | None = None) -> list[SecretGrantRecord]:
        """Ligações em vigor (não revogadas e, com ``agora``, não vencidas)."""
        filtro = [SecretGrantRecord.grantee_type == TIPO, SecretGrantRecord.permission == USO,
                  SecretGrantRecord.revoked_at.is_(None)]
        if segredo_id is not None:
            filtro.append(SecretGrantRecord.secret_id == segredo_id)
        if automation_id is not None:
            filtro.append(SecretGrantRecord.grantee_id == str(automation_id))
        if agora is not None:
            filtro.append(or_(SecretGrantRecord.expires_at.is_(None), SecretGrantRecord.expires_at > agora))
        return list(self.db.scalars(select(SecretGrantRecord).where(and_(*filtro))
                                    .order_by(SecretGrantRecord.created_at)).all())

    def segredos_por_chave(self, chaves: list[str]) -> dict[str, SecretRecord]:
        if not chaves:
            return {}
        linhas = self.db.scalars(select(SecretRecord).where(SecretRecord.key.in_(chaves))).all()
        # Chave repetida em organizações diferentes: vale a primeira ativa (o Portal hoje é de uma organização).
        achados: dict[str, SecretRecord] = {}
        for s in sorted(linhas, key=lambda s: (s.status != "active", s.created_at)):
            achados.setdefault(s.key, s)
        return achados

    def ultimos_usos(self, segredo_ids: list[str]) -> dict[tuple[str, str], datetime]:
        """Última entrega de cada segredo a cada automação (da auditoria)."""
        if not segredo_ids:
            return {}
        linhas = self.db.execute(text(
            "SELECT resource_id, metadata->>'automacao' AS automacao, max(occurred_at) FROM audit_events "
            "WHERE action = 'segredo.entregue' AND resource_type = 'secret' AND resource_id = ANY(:ids) "
            "GROUP BY resource_id, metadata->>'automacao'"), {"ids": segredo_ids}).all()
        return {(r, str(a)): q for r, a, q in linhas if a is not None}

    def contexto_do_job(self, task_execution_id: str, attempt_id: str) -> tuple[int, str, str] | None:
        """(automation_id, execution_id, situação da tentativa)."""
        linha = self.db.execute(text(
            "SELECT v.automation_id, t.execution_id, a.status FROM task_executions t "
            "JOIN automation_versions v ON v.id = t.automation_version_id "
            "JOIN execution_attempts a ON a.id = :a AND a.task_execution_id = t.id WHERE t.id = :t"),
            {"t": task_execution_id, "a": attempt_id}).first()
        return (int(linha[0]), str(linha[1]), str(linha[2])) if linha else None

    def quantos_em_uso(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(SecretGrantRecord)
                                  .where(SecretGrantRecord.grantee_type == TIPO, SecretGrantRecord.revoked_at.is_(None))) or 0)

    # -- escrita -------------------------------------------------------------------------
    def ligar(self, segredo_id: str, automation_id: int, agora: datetime) -> SecretGrantRecord:
        registro = SecretGrantRecord(id=f"sgr_{uuid4().hex}", secret_id=segredo_id, grantee_type=TIPO,
                                     grantee_id=str(automation_id), permission=USO, created_at=agora)
        self.db.add(registro)
        self.db.flush()
        return registro

    def desligar(self, ligacao: SecretGrantRecord, agora: datetime) -> None:
        ligacao.revoked_at = agora
        self.db.flush()

    def mudar(self, segredo: SecretRecord, dados: dict[str, Any], agora: datetime) -> None:
        for campo in ("name", "description", "status"):
            if campo in dados:
                setattr(segredo, campo, dados[campo])
        segredo.updated_at = agora
        self.db.flush()
