"""Limpeza do sistema nas tabelas da Telemetria (regras em ``governance/domain/configuracoes.py``)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from modules.shared.infrastructure.limpeza import apagar_em_lote
from modules.telemetry.infrastructure.orm.models import InboxMessageRecord, NotificationRecord, OutboxMessageRecord


def notificacoes(db: Session, corte: datetime, lote: int) -> int:
    """Notificações (e as entregas, pela chave estrangeira em cascata) criadas antes do corte.

    O detector só olha as últimas 24 h, então uma ocorrência apagada não volta como nova
    (por isso o prazo mínimo é de 2 dias).
    """
    return apagar_em_lote(db, NotificationRecord.id, NotificationRecord.created_at < corte, lote=lote)


def mensagens(db: Session, corte: datetime, lote: int) -> int:
    """Mensagens internas já processadas (entrada) ou publicadas (saída). Pendentes e com erro ficam."""
    entrada = apagar_em_lote(db, InboxMessageRecord.message_id, InboxMessageRecord.status == "processed",
                             InboxMessageRecord.processed_at < corte, lote=lote)
    saida = apagar_em_lote(db, OutboxMessageRecord.id, OutboxMessageRecord.status == "published",
                           OutboxMessageRecord.published_at < corte, lote=lote)
    return entrada + saida
