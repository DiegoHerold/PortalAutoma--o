"""Retenção por automação (Fase 6): ver e definir os dias de imagens, de logs e (Fase 8) de arquivos.

Só quem tem ``admin.system``, como as políticas de retenção. Sem prazo, nada é apagado.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.errors import http_error
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.governance.api.routes import _ensure
from modules.governance.application.retencao import DefinirRetencao
from modules.governance.domain.retencao_por_automacao import DIAS_MAXIMO, DIAS_MINIMO, PrazoInvalido
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.governance.infrastructure.repositories.sqlalchemy_retencao import SqlAlchemyRetencaoPorAutomacao

router = APIRouter(tags=["retencao"])


class PrazoDaAutomacao(BaseModel):
    imagens_dias: int | None = Field(default=None, ge=DIAS_MINIMO, le=DIAS_MAXIMO)
    logs_dias: int | None = Field(default=None, ge=DIAS_MINIMO, le=DIAS_MAXIMO)
    arquivos_dias: int | None = Field(default=None, ge=DIAS_MINIMO, le=DIAS_MAXIMO)


@router.get("/governance/retencao-por-automacao")
def listar(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

    _ensure(db, user, "admin.system")
    prazos = SqlAlchemyRetencaoPorAutomacao(db).todas()
    automacoes = db.execute(select(CatalogAutomationRecord.id, CatalogAutomationRecord.name)
                            .order_by(CatalogAutomationRecord.name)).all()
    return {"limites": {"minimo": DIAS_MINIMO, "maximo": DIAS_MAXIMO}, "automacoes": [{
        "automation_id": i, "automacao": nome,
        "imagens_dias": prazos[i].imagens_dias if i in prazos else None,
        "logs_dias": prazos[i].logs_dias if i in prazos else None,
        "arquivos_dias": prazos[i].arquivos_dias if i in prazos else None,
    } for i, nome in automacoes]}


@router.put("/governance/retencao-por-automacao/{automation_id}")
def definir(automation_id: int, corpo: PrazoDaAutomacao, db: Session = Depends(get_db),
            user: Any = Depends(get_current_user)) -> dict[str, Any]:
    from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

    _ensure(db, user, "admin.system")
    if db.get(CatalogAutomationRecord, automation_id) is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Automação não encontrada.")
    g = build_governance_adapters(db)
    try:
        r = DefinirRetencao(SqlAlchemyRetencaoPorAutomacao(db), g.audit, g.transaction).execute(
            user, automation_id, corpo.imagens_dias, corpo.logs_dias, corpo.arquivos_dias)
    except PrazoInvalido as exc:
        raise http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc)) from exc
    return {"automation_id": r.automation_id, "imagens_dias": r.imagens_dias, "logs_dias": r.logs_dias,
            "arquivos_dias": r.arquivos_dias}
