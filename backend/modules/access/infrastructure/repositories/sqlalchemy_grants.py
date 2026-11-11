"""Concessões por automação (``automation_grants``). Só o Access escreve aqui."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from modules.access.infrastructure.orm.models import (
    AccessTeamRecord,
    AccessUserRecord,
    AutomationGrantRecord,
    TeamMembershipRecord,
)


class SqlAlchemyGrantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _times_ativos(self, user_id: int) -> Any:
        return (select(TeamMembershipRecord.team_id)
                .join(AccessTeamRecord, AccessTeamRecord.id == TeamMembershipRecord.team_id)
                .where(TeamMembershipRecord.user_id == user_id, AccessTeamRecord.status == "active"))

    def acoes_do_usuario(self, user_id: int, automation_id: int) -> set[str]:
        """Ações concedidas ao usuário direto ou a qualquer time ativo dele."""
        linhas = self.db.scalars(select(AutomationGrantRecord.acoes).where(
            AutomationGrantRecord.automation_id == automation_id,
            or_(AutomationGrantRecord.user_id == user_id, AutomationGrantRecord.team_id.in_(self._times_ativos(user_id))),
        )).all()
        return {acao for acoes in linhas for acao in (acoes or [])}

    def listar(self, automation_id: int) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(AutomationGrantRecord, AccessUserRecord.name, AccessUserRecord.email, AccessTeamRecord.name)
            .outerjoin(AccessUserRecord, AccessUserRecord.id == AutomationGrantRecord.user_id)
            .outerjoin(AccessTeamRecord, AccessTeamRecord.id == AutomationGrantRecord.team_id)
            .where(AutomationGrantRecord.automation_id == automation_id)
            .order_by(AutomationGrantRecord.created_at)
        ).all()
        return [{"id": g.id, "automation_id": g.automation_id, "user_id": g.user_id, "team_id": g.team_id,
                 "nome": nome_usuario or nome_time, "email": email, "acoes": list(g.acoes or []),
                 "atualizada_em": g.updated_at.isoformat() if g.updated_at else None}
                for g, nome_usuario, email, nome_time in linhas]

    def buscar(self, automation_id: int, *, user_id: int | None, team_id: int | None) -> AutomationGrantRecord | None:
        filtro = (AutomationGrantRecord.user_id == user_id) if user_id is not None else (AutomationGrantRecord.team_id == team_id)
        return self.db.scalar(select(AutomationGrantRecord).where(AutomationGrantRecord.automation_id == automation_id, filtro))

    def salvar(self, *, grant_id: str, automation_id: int, user_id: int | None, team_id: int | None,
               acoes: list[str], por: int | None, agora: datetime) -> AutomationGrantRecord:
        registro = self.buscar(automation_id, user_id=user_id, team_id=team_id)
        if registro is None:
            registro = AutomationGrantRecord(id=grant_id, automation_id=automation_id, user_id=user_id, team_id=team_id,
                                             acoes=acoes, created_by=por, created_at=agora, updated_at=agora)
            self.db.add(registro)
        else:
            registro.acoes = acoes
            registro.updated_at = agora
        self.db.flush()
        return registro

    def remover(self, registro: AutomationGrantRecord) -> None:
        self.db.delete(registro)
        self.db.flush()

    def existe_usuario(self, user_id: int) -> bool:
        return self.db.get(AccessUserRecord, user_id) is not None

    def existe_time(self, team_id: int) -> bool:
        return self.db.get(AccessTeamRecord, team_id) is not None
