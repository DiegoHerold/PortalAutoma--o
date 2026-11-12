"""Membros e permissões dos times (``access_team_memberships``, ``access_team_category_permissions``).

Só o Access escreve aqui. As concessões por automação dos times ficam em ``sqlalchemy_grants``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from modules.access.application.dto import CategoryPermissionDTO
from modules.access.domain.times import PermissaoDoTime
from modules.access.infrastructure.orm.models import (
    AccessCategoryRecord,
    AccessTeamRecord,
    AccessUserRecord,
    AutomationGrantRecord,
    TeamCategoryPermissionRecord,
    TeamMembershipRecord,
)


class SqlAlchemyTimes:
    def __init__(self, db: Session) -> None:
        self.db = db

    def time(self, team_id: int) -> AccessTeamRecord | None:
        return self.db.get(AccessTeamRecord, team_id)

    def usuarios_existentes(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        return set(self.db.scalars(select(AccessUserRecord.id).where(AccessUserRecord.id.in_(user_ids))))

    def times_existentes(self, team_ids: list[int]) -> set[int]:
        if not team_ids:
            return set()
        return set(self.db.scalars(select(AccessTeamRecord.id).where(AccessTeamRecord.id.in_(team_ids))))

    def categorias_existentes(self, category_ids: list[int]) -> set[int]:
        if not category_ids:
            return set()
        return set(self.db.scalars(select(AccessCategoryRecord.id).where(AccessCategoryRecord.id.in_(category_ids))))

    # -- membros --------------------------------------------------------------------------------
    def membros(self, team_id: int) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(AccessUserRecord.id, AccessUserRecord.name, AccessUserRecord.email, AccessUserRecord.is_active)
            .join(TeamMembershipRecord, TeamMembershipRecord.user_id == AccessUserRecord.id)
            .where(TeamMembershipRecord.team_id == team_id).order_by(AccessUserRecord.name)).all()
        return [{"id": i, "nome": n, "email": e, "ativo": bool(a)} for i, n, e, a in linhas]

    def ids_dos_membros(self, team_id: int) -> set[int]:
        return set(self.db.scalars(select(TeamMembershipRecord.user_id).where(TeamMembershipRecord.team_id == team_id)))

    def adicionar_membros(self, team_id: int, user_ids: set[int]) -> None:
        for user_id in sorted(user_ids - self.ids_dos_membros(team_id)):
            self.db.add(TeamMembershipRecord(team_id=team_id, user_id=user_id))
        self.db.flush()

    def remover_membros(self, team_id: int, user_ids: set[int]) -> None:
        if user_ids:
            self.db.execute(delete(TeamMembershipRecord).where(TeamMembershipRecord.team_id == team_id,
                                                               TeamMembershipRecord.user_id.in_(user_ids)))
            self.db.flush()

    def times_do_usuario(self, user_id: int) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(AccessTeamRecord.id, AccessTeamRecord.name, AccessTeamRecord.status)
            .join(TeamMembershipRecord, TeamMembershipRecord.team_id == AccessTeamRecord.id)
            .where(TeamMembershipRecord.user_id == user_id).order_by(AccessTeamRecord.name)).all()
        return [{"id": i, "nome": n, "situacao": s} for i, n, s in linhas]

    def times_de_todos(self) -> dict[int, list[dict[str, Any]]]:
        saida: dict[int, list[dict[str, Any]]] = {}
        for user_id, team_id, nome in self.db.execute(
                select(TeamMembershipRecord.user_id, AccessTeamRecord.id, AccessTeamRecord.name)
                .join(AccessTeamRecord, AccessTeamRecord.id == TeamMembershipRecord.team_id)
                .order_by(AccessTeamRecord.name)):
            saida.setdefault(user_id, []).append({"id": team_id, "nome": nome})
        return saida

    def definir_times_do_usuario(self, user_id: int, team_ids: set[int]) -> tuple[set[int], set[int]]:
        atuais = set(self.db.scalars(select(TeamMembershipRecord.team_id).where(TeamMembershipRecord.user_id == user_id)))
        entram, saem = team_ids - atuais, atuais - team_ids
        for team_id in sorted(entram):
            self.db.add(TeamMembershipRecord(team_id=team_id, user_id=user_id))
        if saem:
            self.db.execute(delete(TeamMembershipRecord).where(TeamMembershipRecord.user_id == user_id,
                                                               TeamMembershipRecord.team_id.in_(saem)))
        self.db.flush()
        return entram, saem

    # -- permissões ---------------------------------------------------------------------------
    def categorias(self, team_id: int) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(TeamCategoryPermissionRecord, AccessCategoryRecord.name)
            .join(AccessCategoryRecord, AccessCategoryRecord.id == TeamCategoryPermissionRecord.category_id)
            .where(TeamCategoryPermissionRecord.team_id == team_id).order_by(AccessCategoryRecord.name)).all()
        return [{"category_id": p.category_id, "categoria": nome, "can_view": p.can_view, "can_execute": p.can_execute,
                 "can_create": p.can_create, "can_edit": p.can_edit, "can_delete": p.can_delete, "can_approve": p.can_approve}
                for p, nome in linhas]

    def definir_categorias(self, team_id: int, permissoes: list[PermissaoDoTime]) -> None:
        self.db.execute(delete(TeamCategoryPermissionRecord).where(TeamCategoryPermissionRecord.team_id == team_id))
        for p in permissoes:
            self.db.add(TeamCategoryPermissionRecord(team_id=team_id, category_id=p.category_id,
                                                     can_view=p.can_view, can_execute=p.can_execute, can_create=p.can_create,
                                                     can_edit=p.can_edit, can_delete=p.can_delete, can_approve=p.can_approve))
        self.db.flush()

    def automacoes(self, team_id: int) -> list[dict[str, Any]]:
        from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

        linhas = self.db.execute(
            select(AutomationGrantRecord, CatalogAutomationRecord.name)
            .join(CatalogAutomationRecord, CatalogAutomationRecord.id == AutomationGrantRecord.automation_id)
            .where(AutomationGrantRecord.team_id == team_id).order_by(CatalogAutomationRecord.name)).all()
        return [{"automation_id": g.automation_id, "automacao": nome, "acoes": list(g.acoes or [])} for g, nome in linhas]

    def categorias_pelos_times(self, user_id: int) -> list[CategoryPermissionDTO]:
        """O que os times **ativos** da pessoa dão por categoria (para as checagens de acesso)."""
        linhas = self.db.execute(
            select(TeamCategoryPermissionRecord, AccessCategoryRecord.name)
            .join(AccessCategoryRecord, AccessCategoryRecord.id == TeamCategoryPermissionRecord.category_id)
            .join(TeamMembershipRecord, TeamMembershipRecord.team_id == TeamCategoryPermissionRecord.team_id)
            .join(AccessTeamRecord, AccessTeamRecord.id == TeamCategoryPermissionRecord.team_id)
            .where(TeamMembershipRecord.user_id == user_id, AccessTeamRecord.status == "active")).all()
        return [CategoryPermissionDTO(id=None, category_id=p.category_id, category_name=nome, can_view=p.can_view,
                                      can_execute=p.can_execute, can_create=p.can_create, can_edit=p.can_edit,
                                      can_delete=p.can_delete, can_approve=p.can_approve) for p, nome in linhas]
