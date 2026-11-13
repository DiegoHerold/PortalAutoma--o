"""Limpeza do sistema nas tabelas da Fleet (regras em ``governance/domain/configuracoes.py``)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from modules.fleet.infrastructure.orm.models import (
    AgentDiagnosticRecord,
    AgentRegistrationTokenRecord,
    AgentResourceSnapshotRecord,
    DirectChallengeRecord,
    DirectEnrollmentCodeRecord,
    DirectSessionRecord,
    InteractiveSessionSnapshotRecord,
)
from modules.shared.infrastructure.limpeza import apagar_em_lote


def _menos_o_ultimo_de_cada_agent(db: Session, modelo: Any, corte: datetime, lote: int) -> int:
    """Medições antigas, mas a última de cada Agent fica (a tela da máquina mostra a última)."""
    ultimo = select(modelo.id).distinct(modelo.agent_id).order_by(modelo.agent_id, modelo.observed_at.desc())
    return apagar_em_lote(db, modelo.id, modelo.observed_at < corte, modelo.id.not_in(ultimo), lote=lote)


def recursos(db: Session, corte: datetime, lote: int) -> int:
    return _menos_o_ultimo_de_cada_agent(db, AgentResourceSnapshotRecord, corte, lote)


def sessoes(db: Session, corte: datetime, lote: int) -> int:
    return _menos_o_ultimo_de_cada_agent(db, InteractiveSessionSnapshotRecord, corte, lote)


def diagnosticos(db: Session, corte: datetime, lote: int) -> int:
    return apagar_em_lote(db, AgentDiagnosticRecord.id, AgentDiagnosticRecord.completed_at < corte, lote=lote)


def sessoes_diretas(db: Session, corte: datetime, lote: int) -> int:
    """Sessões e desafios de login do modo direto vencidos (ou revogados/usados) antes do corte."""
    sessoes_vencidas = apagar_em_lote(
        db, DirectSessionRecord.id,
        or_(DirectSessionRecord.expires_at < corte, DirectSessionRecord.revoked_at < corte), lote=lote)
    desafios = apagar_em_lote(
        db, DirectChallengeRecord.id,
        or_(DirectChallengeRecord.expires_at < corte, DirectChallengeRecord.used_at < corte), lote=lote)
    return sessoes_vencidas + desafios


def codigos_vencidos(db: Session, corte: datetime, lote: int) -> int:
    """Códigos de cadastro que venceram sem uso. Os usados ficam (mostram quem cadastrou o quê)."""
    agents = apagar_em_lote(
        db, AgentRegistrationTokenRecord.id,
        AgentRegistrationTokenRecord.used_at.is_(None), AgentRegistrationTokenRecord.expires_at < corte, lote=lote)
    diretas = apagar_em_lote(
        db, DirectEnrollmentCodeRecord.id,
        DirectEnrollmentCodeRecord.used_at.is_(None), DirectEnrollmentCodeRecord.expires_at < corte, lote=lote)
    return agents + diretas
