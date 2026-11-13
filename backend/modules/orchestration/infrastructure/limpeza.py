"""Limpeza do sistema nas tabelas da Orchestration (regras em ``governance/domain/configuracoes.py``)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from modules.orchestration.infrastructure.orm.models import WebhookChamadaRecord
from modules.shared.infrastructure.limpeza import apagar_em_lote


def chamadas_de_webhook(db: Session, corte: datetime, lote: int) -> int:
    """Histórico das chamadas recebidas. O limite por minuto olha o último minuto e a proteção
    contra repetição, as últimas 24 h: por isso o prazo mínimo é de 7 dias."""
    return apagar_em_lote(db, WebhookChamadaRecord.id, WebhookChamadaRecord.recebida_em < corte, lote=lote)
