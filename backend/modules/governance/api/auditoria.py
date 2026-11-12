"""API da tela de Auditoria (12/11/2026).

- ``GET /governance/auditoria/eventos``: a linha do tempo, da mais nova, com filtros (período,
  pessoa, tipo, ação, recurso, mesma ação) e ``antes`` para carregar mais.
- ``GET /governance/auditoria/grupos?por=dia|usuario|acao``: quantos eventos em cada grupo.
- ``GET /governance/auditoria/pessoas``: quem aparece na auditoria (para o filtro).
- ``POST /governance/auditoria/tela``: a tela que a pessoa abriu (qualquer pessoa logada).

Ler a auditoria exige ``audit.read``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.governance.api.routes import _ensure
from modules.governance.domain.audit import AuditEvent
from modules.governance.domain.auditoria import FiltroInvalido, intervalo, validar_agrupamento, validar_tipo
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.governance.infrastructure.orm.models import AuditEventRecord
from modules.governance.infrastructure.repositories.sqlalchemy_auditoria import Filtros, SqlAlchemyAuditoria

router = APIRouter(prefix="/governance/auditoria", tags=["governance"])

TELA_REPETIDA = timedelta(minutes=2)


def _filtros(de: date | None, ate: date | None, usuario: str | None, tipo: str | None, acao: str | None,
             recurso_tipo: str | None, recurso_id: str | None, correlacao: str | None, busca: str | None,
             tecnicos: bool) -> Filtros:
    try:
        inicio, fim = intervalo(de, ate)
        return Filtros(de=inicio, ate=fim, usuario=usuario or None, tipo=validar_tipo(tipo), acao=acao or None,
                       recurso_tipo=recurso_tipo or None, recurso_id=recurso_id or None, correlacao=correlacao or None,
                       busca=busca, tecnicos=tecnicos)
    except FiltroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _parametros(de: date | None = None, ate: date | None = None, usuario: str | None = Query(None, max_length=80),
                tipo: str | None = None, acao: str | None = Query(None, max_length=120),
                recurso_tipo: str | None = Query(None, max_length=120), recurso_id: str | None = Query(None, max_length=120),
                correlacao: str | None = Query(None, max_length=120), busca: str | None = Query(None, max_length=120),
                tecnicos: bool = False) -> Filtros:
    return _filtros(de, ate, usuario, tipo, acao, recurso_tipo, recurso_id, correlacao, busca, tecnicos)


def _com_email(auditoria: SqlAlchemyAuditoria, f: Filtros) -> Filtros:
    from dataclasses import replace

    return replace(f, usuario_email=auditoria.email_de(f.usuario)) if f.usuario else f


@router.get("/eventos")
def eventos(filtros: Filtros = Depends(_parametros), antes: datetime | None = None, limite: int = Query(60, ge=1, le=300),
            db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "audit.read")
    auditoria = SqlAlchemyAuditoria(db)
    linhas = auditoria.eventos(_com_email(auditoria, filtros), antes=antes, limite=limite)
    return {"eventos": linhas, "cursor": linhas[-1]["quando"] if len(linhas) == limite else None}


@router.get("/grupos")
def grupos(por: str = Query("dia"), filtros: Filtros = Depends(_parametros), db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "audit.read")
    try:
        agrupamento = validar_agrupamento(por)
    except FiltroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    auditoria = SqlAlchemyAuditoria(db)
    return {"por": agrupamento, "grupos": auditoria.grupos(_com_email(auditoria, filtros), agrupamento)}


@router.get("/pessoas")
def pessoas(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _ensure(db, user, "audit.read")
    return {"pessoas": SqlAlchemyAuditoria(db).pessoas()}


@router.post("/tela", status_code=204, response_model=None)
def tela_aberta(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    """A tela que a pessoa abriu. A mesma tela de novo em menos de 2 min não repete o registro."""
    caminho = str(corpo.get("caminho") or "").strip()[:120]
    if not caminho.startswith("/"):
        raise HTTPException(status_code=422, detail="caminho: a tela aberta, como /historico")
    quem = str(getattr(user, "id", "")) or None
    agora = datetime.now(UTC)
    ultima = db.scalar(select(AuditEventRecord.resource_id).where(
        AuditEventRecord.actor_id == quem, AuditEventRecord.action == "tela.aberta").order_by(AuditEventRecord.occurred_at.desc()).limit(1)
        .where(AuditEventRecord.occurred_at >= agora - TELA_REPETIDA))
    if ultima == caminho:
        return None
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=quem, action="tela.aberta", resource_type="tela",
        resource_id=caminho, metadata={"titulo": str(corpo.get("titulo") or "")[:120] or None}, occurred_at=agora))
    db.commit()
    return None
