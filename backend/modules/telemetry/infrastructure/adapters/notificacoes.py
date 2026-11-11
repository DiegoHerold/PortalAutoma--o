"""Montagem das notificações e da retenção (Fase 6), para as tarefas periódicas e a API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from modules.telemetry.application.use_cases.notificacoes import DetectarOcorrencias, EnviarAvisos
from modules.telemetry.infrastructure.email_graph import montar_carteiro
from modules.telemetry.infrastructure.repositories.sqlalchemy_notificacoes import (
    SqlAlchemyLeituraDeOcorrencias,
    SqlAlchemyNotificacoes,
)


class _Transacao:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()


def build_detectar(db: Session) -> DetectarOcorrencias:
    from modules.access.api.authorization import acesso_por_automacao
    from modules.access.application.use_cases import PermissionChecker
    from modules.access.domain.concessao import CENTRAL_DE_TELAS, VER_EXECUCOES
    from modules.access.infrastructure.adapters import build_access_adapters
    from modules.dispatch.infrastructure.adapters.fila import build_fila

    acesso = acesso_por_automacao(db)
    checador = PermissionChecker(build_access_adapters(db).access)

    def pode_ver(usuario: Any, automation_id: int) -> bool:
        return checador.has_permission(usuario, CENTRAL_DE_TELAS) or acesso.pode(usuario, automation_id, VER_EXECUCOES)

    def ver_fila(agora: datetime) -> dict[str, Any]:
        return build_fila(db).ver.execute(agora)

    return DetectarOcorrencias(SqlAlchemyLeituraDeOcorrencias(db), SqlAlchemyNotificacoes(db), ver_fila, pode_ver,
                               _Transacao(db))


def build_enviar(db: Session, carteiro: Any | None = None) -> EnviarAvisos:
    settings = get_settings()
    return EnviarAvisos(SqlAlchemyNotificacoes(db), carteiro if carteiro is not None else montar_carteiro(settings),
                        _Transacao(db), settings.frontend_url)


def build_aplicar_retencao(db: Session):
    from modules.governance.application.retencao import AplicarRetencao
    from modules.governance.infrastructure.adapters import build_governance_adapters
    from modules.governance.infrastructure.repositories.sqlalchemy_retencao import SqlAlchemyRetencaoPorAutomacao
    from modules.storage.application.use_cases.objetos import ApagarObjeto
    from modules.storage.infrastructure.adapters import build_storage_adapters
    from modules.telemetry.infrastructure.repositories.sqlalchemy_retencao import SqlAlchemyRetencaoDaTelemetria

    storage = build_storage_adapters(db)
    governanca = build_governance_adapters(db)
    telemetria = SqlAlchemyRetencaoDaTelemetria(db, ApagarObjeto(storage.object_storage, storage.stored_objects))
    return AplicarRetencao(SqlAlchemyRetencaoPorAutomacao(db), telemetria, governanca.audit, _Transacao(db))
