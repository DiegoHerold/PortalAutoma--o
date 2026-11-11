"""Instâncias diretas: códigos de inscrição, instâncias, desafios e sessões (Fleet escreve)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modules.fleet.infrastructure.orm.models import (
    DirectChallengeRecord,
    DirectEnrollmentCodeRecord,
    DirectInstanceRecord,
    DirectSessionRecord,
    MachineRecord,
)


class SqlAlchemyDirectInstanceStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- códigos -------------------------------------------------------------------------
    def adicionar_codigo(self, **campos: Any) -> None:
        self.db.add(DirectEnrollmentCodeRecord(**campos))
        self.db.flush()

    def reservar_codigo(self, code_hash: str, agora: datetime) -> tuple[str, int] | None:
        """Trava o código válido (FOR UPDATE): duas inscrições com o mesmo código, só uma passa."""
        linha = self.db.execute(
            select(DirectEnrollmentCodeRecord.id, DirectEnrollmentCodeRecord.automation_id)
            .where(DirectEnrollmentCodeRecord.code_hash == code_hash, DirectEnrollmentCodeRecord.used_at.is_(None),
                   DirectEnrollmentCodeRecord.expires_at > agora)
            .with_for_update()
        ).first()
        return (linha[0], linha[1]) if linha else None

    def marcar_codigo_usado(self, codigo_id: str, instancia_id: str, agora: datetime) -> None:
        self.db.execute(update(DirectEnrollmentCodeRecord).where(DirectEnrollmentCodeRecord.id == codigo_id)
                        .values(used_at=agora, direct_instance_id=instancia_id))

    # -- instâncias ------------------------------------------------------------------------
    def adicionar_instancia(self, **campos: Any) -> None:
        self.db.add(DirectInstanceRecord(**campos))
        self.db.flush()

    def instancia(self, instancia_id: str) -> DirectInstanceRecord | None:
        return self.db.get(DirectInstanceRecord, instancia_id)

    def da_automacao(self, automation_id: int) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(DirectInstanceRecord, MachineRecord.name)
            .outerjoin(MachineRecord, MachineRecord.id == DirectInstanceRecord.machine_id)
            .where(DirectInstanceRecord.automation_id == automation_id)
            .order_by(DirectInstanceRecord.created_at.desc())
        ).all()
        return [{"id": i.id, "status": i.status, "nome_informado": i.reported_name, "versao": i.reported_version,
                 "maquina_id": i.machine_id, "maquina_nome": nome, "inscrita_em": _iso(i.created_at),
                 "aprovada_em": _iso(i.approved_at), "aprovada_por": i.approved_by, "revogada_em": _iso(i.revoked_at),
                 "ultimo_sinal": _iso(i.last_seen_at)} for i, nome in linhas]

    def todas(self) -> list[dict[str, Any]]:
        """Todas as instâncias (revogadas por último), com o nome da automação."""
        from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

        linhas = self.db.execute(
            select(DirectInstanceRecord, MachineRecord.name, CatalogAutomationRecord.name)
            .outerjoin(MachineRecord, MachineRecord.id == DirectInstanceRecord.machine_id)
            .outerjoin(CatalogAutomationRecord, CatalogAutomationRecord.id == DirectInstanceRecord.automation_id)
            .order_by((DirectInstanceRecord.status == "revogada"), DirectInstanceRecord.created_at.desc())
        ).all()
        return [{"id": i.id, "status": i.status, "automation_id": i.automation_id, "automacao": automacao,
                 "nome_informado": i.reported_name, "versao": i.reported_version, "maquina_id": i.machine_id,
                 "maquina_nome": nome, "inscrita_em": _iso(i.created_at), "ultimo_sinal": _iso(i.last_seen_at)}
                for i, nome, automacao in linhas]

    def maquina_existe(self, machine_id: str) -> bool:
        return self.db.scalar(select(MachineRecord.id).where(MachineRecord.id == machine_id,
                                                              MachineRecord.status == "ativa")) is not None

    def revogar_sessoes(self, instancia_id: str, agora: datetime) -> None:
        self.db.execute(update(DirectSessionRecord).where(DirectSessionRecord.direct_instance_id == instancia_id,
                                                         DirectSessionRecord.revoked_at.is_(None))
                        .values(revoked_at=agora))

    # -- desafio e sessão ------------------------------------------------------------------
    def adicionar_desafio(self, **campos: Any) -> None:
        self.db.add(DirectChallengeRecord(**campos))
        self.db.flush()

    def usar_desafio(self, desafio_id: str, instancia_id: str, agora: datetime) -> str | None:
        """Consome o desafio (uso único). Devolve o nonce, ou None se vencido, usado ou de outra."""
        linha = self.db.execute(
            update(DirectChallengeRecord)
            .where(DirectChallengeRecord.id == desafio_id, DirectChallengeRecord.direct_instance_id == instancia_id,
                   DirectChallengeRecord.used_at.is_(None), DirectChallengeRecord.expires_at > agora)
            .values(used_at=agora).returning(DirectChallengeRecord.nonce)
        ).first()
        return linha[0] if linha else None

    def adicionar_sessao(self, **campos: Any) -> None:
        self.db.add(DirectSessionRecord(**campos))
        self.db.flush()

    def sessao(self, token_hash: str) -> tuple[DirectSessionRecord, DirectInstanceRecord] | None:
        linha = self.db.execute(
            select(DirectSessionRecord, DirectInstanceRecord)
            .join(DirectInstanceRecord, DirectInstanceRecord.id == DirectSessionRecord.direct_instance_id)
            .where(DirectSessionRecord.token_hash == token_hash)
        ).first()
        return (linha[0], linha[1]) if linha else None


class SqlAlchemyMachineStore:
    """Cadastro de máquinas pelo administrador (com ou sem Agent, ADR-019)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar(self) -> list[dict[str, Any]]:
        return [{"id": m.id, "nome": m.name, "status": m.status, "capacidade": m.pool_capacity}
                for m in self.db.scalars(select(MachineRecord).order_by(MachineRecord.name))]

    def nome_em_uso(self, nome: str) -> bool:
        return self.db.scalar(select(MachineRecord.id).where(MachineRecord.name == nome,
                                                              MachineRecord.status == "ativa")) is not None

    def adicionar(self, *, machine_id: str, nome: str) -> None:
        self.db.add(MachineRecord(id=machine_id, name=nome))
        self.db.flush()


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None
