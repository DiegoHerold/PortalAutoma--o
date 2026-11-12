"""Papéis globais no PostgreSQL (Access)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from modules.access.infrastructure.orm.models import (
    AccessRoleRecord,
    AccessUserRecord,
    PermissionRecord,
    RolePermissionRecord,
    UserRoleRecord,
)


class SqlAlchemyPapeis:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _linha(self, r: AccessRoleRecord, pessoas: int) -> dict[str, Any]:
        return {"id": r.id, "nome": r.name, "slug": r.slug, "descricao": r.description, "abas": r.abas,
                "funcionalidades": r.funcionalidades, "gravadas": sorted(self.permissoes(r.id)), "pessoas": pessoas}

    def _pessoas(self) -> dict[int, int]:
        return dict(self.db.execute(select(AccessUserRecord.role_id, func.count()).group_by(AccessUserRecord.role_id)).all())

    def listar(self) -> list[dict[str, Any]]:
        pessoas = self._pessoas()
        ordem = {"admin": 0, "manager": 1, "operator": 2, "viewer": 3}
        papeis = sorted(self.db.scalars(select(AccessRoleRecord)).all(), key=lambda r: (ordem.get(r.slug, 9), r.name.lower()))
        return [self._linha(r, pessoas.get(r.id, 0)) for r in papeis]

    def obter(self, papel_id: int) -> dict[str, Any] | None:
        r = self.db.get(AccessRoleRecord, papel_id)
        return None if r is None else self._linha(r, self._pessoas().get(r.id, 0))

    def slugs(self) -> set[str]:
        return set(self.db.scalars(select(AccessRoleRecord.slug)).all())

    def nome_em_uso(self, nome: str, exceto: int | None = None) -> bool:
        consulta = select(AccessRoleRecord.id).where(func.lower(AccessRoleRecord.name) == nome.lower())
        if exceto is not None:
            consulta = consulta.where(AccessRoleRecord.id != exceto)
        return self.db.scalar(consulta.limit(1)) is not None

    def criar(self, *, nome: str, slug: str, descricao: str | None, funcionalidades: dict[str, str]) -> int:
        r = AccessRoleRecord(name=nome, slug=slug, description=descricao, status="active", is_system=False,
                             funcionalidades=funcionalidades)
        self.db.add(r)
        self.db.flush()
        return r.id

    def alterar(self, papel_id: int, campos: dict[str, Any]) -> None:
        colunas = {"nome": "name", "descricao": "description", "funcionalidades": "funcionalidades"}
        self.db.execute(update(AccessRoleRecord).where(AccessRoleRecord.id == papel_id)
                        .values(**{colunas[k]: v for k, v in campos.items()}))

    def permissoes(self, papel_id: int) -> set[str]:
        return set(self.db.scalars(select(RolePermissionRecord.permission_key).where(RolePermissionRecord.role_id == papel_id)))

    def dar_permissoes(self, papel_id: int, chaves: list[str]) -> None:
        existentes = set(self.db.scalars(select(PermissionRecord.key)))
        ja = self.permissoes(papel_id)
        for chave in chaves:
            if chave in existentes and chave not in ja:
                self.db.add(RolePermissionRecord(role_id=papel_id, permission_key=chave))
                ja.add(chave)
        self.db.flush()

    def mover_pessoas(self, de: int, para: int) -> int:
        movidas = self.db.execute(update(AccessUserRecord).where(AccessUserRecord.role_id == de).values(role_id=para)).rowcount
        # Papéis extras por organização: quem já tinha o substituto fica só com ele.
        for vinculo in self.db.scalars(select(UserRoleRecord).where(UserRoleRecord.role_id == de)).all():
            repetido = self.db.scalar(select(UserRoleRecord.id).where(
                UserRoleRecord.user_id == vinculo.user_id, UserRoleRecord.role_id == para,
                UserRoleRecord.organization_id.is_(None) if vinculo.organization_id is None
                else UserRoleRecord.organization_id == vinculo.organization_id))
            if repetido is None:
                vinculo.role_id = para
            else:
                self.db.delete(vinculo)
        self.db.flush()
        return int(movidas or 0)

    def apagar(self, papel_id: int) -> None:
        self.db.execute(delete(RolePermissionRecord).where(RolePermissionRecord.role_id == papel_id))
        self.db.execute(delete(AccessRoleRecord).where(AccessRoleRecord.id == papel_id))
        self.db.flush()
