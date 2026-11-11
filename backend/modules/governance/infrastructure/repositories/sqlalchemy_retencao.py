from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from modules.governance.domain.retencao_por_automacao import RetencaoDaAutomacao
from modules.governance.infrastructure.orm.models import AutomationRetentionRecord


def _dominio(linha: AutomationRetentionRecord) -> RetencaoDaAutomacao:
    return RetencaoDaAutomacao(linha.automation_id, linha.imagens_dias, linha.logs_dias)


class SqlAlchemyRetencaoPorAutomacao:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, automation_id: int) -> RetencaoDaAutomacao | None:
        linha = self.db.get(AutomationRetentionRecord, automation_id)
        return _dominio(linha) if linha else None

    def todas(self) -> dict[int, RetencaoDaAutomacao]:
        return {linha.automation_id: _dominio(linha) for linha in self.db.scalars(select(AutomationRetentionRecord))}

    def com_prazo(self) -> list[RetencaoDaAutomacao]:
        return [_dominio(linha) for linha in self.db.scalars(
            select(AutomationRetentionRecord)
            .where(or_(AutomationRetentionRecord.imagens_dias.is_not(None), AutomationRetentionRecord.logs_dias.is_not(None)))
            .order_by(AutomationRetentionRecord.automation_id))]

    def gravar(self, retencao: RetencaoDaAutomacao, por: str | None) -> None:
        linha = self.db.get(AutomationRetentionRecord, retencao.automation_id)
        if linha is None:
            linha = AutomationRetentionRecord(automation_id=retencao.automation_id)
            self.db.add(linha)
        linha.imagens_dias = retencao.imagens_dias
        linha.logs_dias = retencao.logs_dias
        linha.updated_by = por
        self.db.flush()
