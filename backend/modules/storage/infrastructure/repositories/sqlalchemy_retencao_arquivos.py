"""Retenção do lado do Storage (Fase 8): apaga os arquivos que a automação entregou.

Governance decide o prazo e chama aqui. Os bytes saem por ``ApagarObjeto``; o artefato fica,
marcado ``deleted``, para a tela e o download dizerem "apagado pela retenção". As imagens dos
passos (``passos/...``) seguem o prazo de imagens, na Telemetria, e não entram aqui.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import not_, or_, select
from sqlalchemy.orm import Session

from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord
from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
from modules.storage.infrastructure.orm.models import ArtifactRecord

LOTE = 500


class SqlAlchemyRetencaoDosArquivos:
    def __init__(self, db: Session, apagar_objeto: Any) -> None:
        self.db = db
        self.apagar_objeto = apagar_objeto

    def apagar_arquivos(self, automation_id: int, antes_de: datetime, limite: int = LOTE) -> int:
        linhas = list(self.db.scalars(
            select(ArtifactRecord)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ArtifactRecord.task_execution_id)
            .join(CatalogAutomationVersionRecord, CatalogAutomationVersionRecord.id == TaskExecutionRecord.automation_version_id)
            .where(CatalogAutomationVersionRecord.automation_id == automation_id, ArtifactRecord.created_at < antes_de,
                   ArtifactRecord.status == "available",
                   not_(or_(ArtifactRecord.name.like("passos/%"), ArtifactRecord.name.like("passos\\%"))))
            .order_by(ArtifactRecord.created_at).limit(limite)
        ))
        agora = datetime.now(UTC)
        for linha in linhas:
            if linha.stored_object_id:
                self.apagar_objeto.execute(linha.stored_object_id)
            linha.status = "deleted"
            linha.artifact_metadata = {**(linha.artifact_metadata or {}), "apagado_em": agora.isoformat(),
                                       "apagado_por": "retencao"}
        self.db.flush()
        return len(linhas)
