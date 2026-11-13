"""Contas de serviço (13/11/2026): a conta e o usuário técnico dela. Só o Access escreve aqui."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from modules.access.infrastructure.orm.models import (
    AccessRoleRecord,
    AccessUserRecord,
    ServiceAccountRecord,
    TeamMembershipRecord,
)


class SqlAlchemyContasDeServico:
    def __init__(self, db: Session) -> None:
        self.db = db

    def todas(self) -> list[ServiceAccountRecord]:
        return list(self.db.scalars(select(ServiceAccountRecord).order_by(ServiceAccountRecord.name)).all())

    def conta(self, conta_id: str) -> ServiceAccountRecord | None:
        return self.db.get(ServiceAccountRecord, conta_id)

    def pelo_hash(self, credential_hash: str) -> ServiceAccountRecord | None:
        return self.db.scalar(select(ServiceAccountRecord).where(ServiceAccountRecord.credential_hash == credential_hash))

    def usuario(self, user_id: int | None) -> AccessUserRecord | None:
        return self.db.get(AccessUserRecord, user_id) if user_id is not None else None

    def papel(self, role_id: int) -> AccessRoleRecord | None:
        return self.db.get(AccessRoleRecord, role_id)

    def nome_existe(self, nome: str, exceto: str | None = None) -> bool:
        consulta = select(ServiceAccountRecord.id).where(ServiceAccountRecord.name.ilike(nome))
        if exceto:
            consulta = consulta.where(ServiceAccountRecord.id != exceto)
        return self.db.scalar(consulta) is not None

    def criar(self, *, conta_id: str, nome: str, descricao: str | None, role_id: int, organization_id: int | None,
              credential_hash: str, hint: str, expira_em: datetime | None, criado_por: str | None,
              senha_inutilizavel: str, agora: datetime) -> ServiceAccountRecord:
        usuario = AccessUserRecord(name=nome, email=f"{conta_id}@contas-de-servico.invalid", password_hash=senha_inutilizavel,
                                   role_id=role_id, organization_id=organization_id, status="active", is_active=True,
                                   created_at=agora, updated_at=agora)
        self.db.add(usuario)
        self.db.flush()
        conta = ServiceAccountRecord(id=conta_id, organization_id=organization_id, name=nome, description=descricao,
                                     status="active", credential_hash=credential_hash, credential_hint=hint,
                                     credential_created_at=agora, permissions=[], expires_at=expira_em,
                                     user_id=usuario.id, created_by=criado_por, created_at=agora)
        self.db.add(conta)
        self.db.flush()
        return conta

    def mudar(self, conta: ServiceAccountRecord, dados: dict[str, Any], agora: datetime) -> None:
        usuario = self.usuario(conta.user_id)
        for campo, valor in dados.items():
            setattr(conta, campo, valor)
        if usuario is not None:
            if "name" in dados:
                usuario.name = dados["name"]
            usuario.updated_at = agora
        self.db.flush()

    def mudar_papel(self, conta: ServiceAccountRecord, role_id: int, agora: datetime) -> None:
        usuario = self.usuario(conta.user_id)
        if usuario is not None:
            usuario.role_id = role_id
            usuario.updated_at = agora
            self.db.flush()

    def trocar_credencial(self, conta: ServiceAccountRecord, credential_hash: str, hint: str, agora: datetime) -> None:
        conta.credential_hash = credential_hash
        conta.credential_hint = hint
        conta.credential_created_at = agora
        conta.revoked_at = None
        self.db.flush()

    def marcar_uso(self, conta: ServiceAccountRecord, agora: datetime) -> None:
        conta.last_used_at = agora
        self.db.flush()

    def apagar(self, conta: ServiceAccountRecord) -> None:
        user_id = conta.user_id
        self.db.delete(conta)
        self.db.flush()
        if user_id is not None:
            self.db.execute(delete(TeamMembershipRecord).where(TeamMembershipRecord.user_id == user_id))
            usuario = self.usuario(user_id)
            if usuario is not None:
                self.db.delete(usuario)
        self.db.flush()

    def ids_dos_usuarios_tecnicos(self) -> set[int]:
        return {u for u in self.db.scalars(select(ServiceAccountRecord.user_id).where(ServiceAccountRecord.user_id.is_not(None)))}
