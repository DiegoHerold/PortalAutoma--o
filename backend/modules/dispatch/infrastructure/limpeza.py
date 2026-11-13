"""Limpeza do sistema nas tabelas do Dispatch (regras em ``governance/domain/configuracoes.py``)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from modules.dispatch.infrastructure.orm.models import (
    AgentCommandRecord,
    DirectCommandRecord,
    DispatchDecisionRecord,
    JobTokenRecord,
    ReconciliationRecord,
)
from modules.shared.infrastructure.limpeza import apagar_em_lote

COMANDO_EM_ANDAMENTO = ("pending", "sent")


def comandos(db: Session, corte: datetime, lote: int) -> int:
    """Comandos concluídos: para os Agents (fora de pendente/enviado) e para o modo direto (entregues)."""
    agents = apagar_em_lote(db, AgentCommandRecord.id, AgentCommandRecord.status.not_in(COMANDO_EM_ANDAMENTO),
                            AgentCommandRecord.created_at < corte, lote=lote)
    diretos = apagar_em_lote(db, DirectCommandRecord.id, DirectCommandRecord.status != "pendente",
                             DirectCommandRecord.created_at < corte, lote=lote)
    return agents + diretos


def tokens_de_job(db: Session, corte: datetime, lote: int) -> int:
    return apagar_em_lote(db, JobTokenRecord.id,
                          or_(JobTokenRecord.expires_at < corte, JobTokenRecord.revoked_at < corte), lote=lote)


def decisoes(db: Session, corte: datetime, lote: int) -> int:
    return apagar_em_lote(db, DispatchDecisionRecord.id, DispatchDecisionRecord.created_at < corte, lote=lote)


def reconciliacoes(db: Session, corte: datetime, lote: int) -> int:
    return apagar_em_lote(db, ReconciliationRecord.id, ReconciliationRecord.completed_at < corte, lote=lote)
