"""Apoio às regras de limpeza do sistema (catálogo em ``governance/domain/configuracoes.py``).

Cada contexto apaga só as próprias tabelas (``<contexto>/infrastructure/limpeza.py``) e cada
função tem a forma ``(db, corte, lote) -> quantos saíram``. ``apagar_em_lote`` apaga no máximo
``lote`` linhas por chamada, para não segurar o banco; a próxima passada continua.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from modules.shared.infrastructure.orm.models import IdempotencyRecordModel


def apagar_em_lote(db: Session, coluna_id: Any, *condicoes: Any, lote: int) -> int:
    tabela = coluna_id.class_
    ids = select(coluna_id).where(*condicoes).limit(lote).scalar_subquery()
    resultado = db.execute(delete(tabela).where(coluna_id.in_(ids)).execution_options(synchronize_session=False))
    return int(resultado.rowcount or 0)


def idempotencia(db: Session, corte: datetime, lote: int) -> int:
    """Registros contra pedido repetido que venceram antes do corte."""
    return apagar_em_lote(db, IdempotencyRecordModel.id, IdempotencyRecordModel.expires_at < corte, lote=lote)
