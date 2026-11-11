"""Retenção do lado da Telemetria (Fase 6): apaga imagens e logs de uma automação.

Governance decide o prazo e chama aqui; os bytes das imagens saem pelo Storage
(``ApagarObjeto``). A linha da imagem fica, marcada ``apagada_em``, para a tela dizer
"apagada pela retenção" em vez de "não encontrada". Etapas, progresso e ``step_runs``
ficam: a estimativa não muda por causa da limpeza.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord
from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
from modules.telemetry.infrastructure.orm.models import ExecutionEventRecord, StepImageRecord

LOTE = 500


class SqlAlchemyRetencaoDaTelemetria:
    def __init__(self, db: Session, apagar_objeto: Any) -> None:
        self.db = db
        self.apagar_objeto = apagar_objeto

    def apagar_imagens(self, automation_id: int, antes_de: datetime, limite: int = LOTE) -> int:
        linhas = list(self.db.scalars(
            select(StepImageRecord)
            .where(StepImageRecord.automation_id == automation_id, StepImageRecord.created_at < antes_de,
                   StepImageRecord.apagada_em.is_(None))
            .order_by(StepImageRecord.created_at).limit(limite)
        ))
        agora = datetime.now(UTC)
        for linha in linhas:
            for campo in ("cheia_id", "media_id", "miniatura_id"):
                objeto = getattr(linha, campo)
                if objeto:
                    self.apagar_objeto.execute(objeto)
                    setattr(linha, campo, None)
            linha.apagada_em = agora
        self.db.flush()
        return len(linhas)

    def apagar_logs(self, automation_id: int, antes_de: datetime, limite: int = LOTE * 10) -> int:
        """Só as linhas de log (contrato novo e stdout/stderr antigos), nada mais."""
        e_log = or_(ExecutionEventRecord.event_type.in_(["log", "warning", "error"]),
                    and_(ExecutionEventRecord.event_type == "automation.event",
                         ExecutionEventRecord.payload["type"].astext == "log"))
        ids = select(ExecutionEventRecord.id).join(
            TaskExecutionRecord, TaskExecutionRecord.id == ExecutionEventRecord.task_execution_id
        ).join(
            CatalogAutomationVersionRecord, CatalogAutomationVersionRecord.id == TaskExecutionRecord.automation_version_id
        ).where(
            CatalogAutomationVersionRecord.automation_id == automation_id, ExecutionEventRecord.received_at < antes_de, e_log
        ).limit(limite)
        resultado = self.db.execute(delete(ExecutionEventRecord).where(ExecutionEventRecord.id.in_(ids.scalar_subquery())))
        return int(resultado.rowcount or 0)
