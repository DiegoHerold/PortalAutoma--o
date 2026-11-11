"""Arquivos que a automação entregou (Fase 8): a aba Arquivos no Catálogo.

Planilhas e TXT têm dados da folha: ver e baixar exigem ``ver_telas_e_logs`` na automação
(decisão de 11/11/2026), e todo download vai para a auditoria. Os bytes só saem pela API;
nunca há endereço público. As imagens dos passos (``passos/...``) não entram aqui.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import not_, or_, select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import ensure_automation_grant
from modules.access.api.dependencies import get_current_user
from modules.access.domain.concessao import VER_TELAS_E_LOGS
from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
from modules.storage.application.use_cases.objetos import LerObjeto
from modules.storage.domain.errors import ArtifactNotFound
from modules.storage.infrastructure.adapters import build_storage_adapters
from modules.storage.infrastructure.orm.models import ArtifactRecord

router = APIRouter(prefix="/automations/{automation_id}/arquivos", tags=["storage"])

NAO_E_PASSO = not_(or_(ArtifactRecord.name.like("passos/%"), ArtifactRecord.name.like("passos\\%")))


def _da_automacao(automation_id: int) -> Any:
    return (select(ArtifactRecord, TaskExecutionRecord.execution_id)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ArtifactRecord.task_execution_id)
            .join(CatalogAutomationVersionRecord, CatalogAutomationVersionRecord.id == TaskExecutionRecord.automation_version_id)
            .where(CatalogAutomationVersionRecord.automation_id == automation_id, NAO_E_PASSO))


def _publico(a: ArtifactRecord) -> dict[str, Any]:
    meta = a.artifact_metadata or {}
    return {"id": a.id, "nome": a.name, "tipo": a.content_type, "bytes": a.size_bytes, "situacao": a.status,
            "execucao_id": a.execution_id, "job_id": a.task_execution_id, "item": meta.get("item"),
            "quando": (a.uploaded_at or a.created_at).isoformat() if (a.uploaded_at or a.created_at) else None}


@router.get("")
def listar(automation_id: int, busca: str | None = Query(default=None, max_length=120),
           antes: str | None = Query(default=None, max_length=40), limite: int = Query(default=50, ge=1, le=200),
           db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    ensure_automation_grant(db, user, automation_id, VER_TELAS_E_LOGS)
    consulta = _da_automacao(automation_id).where(ArtifactRecord.status == "available")
    if busca and busca.strip():
        consulta = consulta.where(or_(ArtifactRecord.name.ilike(f"%{busca.strip()}%"),
                                     ArtifactRecord.artifact_metadata["item"].astext == busca.strip()))
    if antes:
        try:
            corte = datetime.fromisoformat(antes)
        except ValueError:
            raise HTTPException(status_code=422, detail="antes: data inválida") from None
        consulta = consulta.where(ArtifactRecord.created_at < corte)
    linhas = db.execute(consulta.order_by(ArtifactRecord.created_at.desc()).limit(limite)).all()
    arquivos = [_publico(a) for a, _ in linhas]
    return {"arquivos": arquivos,
            "cursor": linhas[-1][0].created_at.isoformat() if len(linhas) == limite else None}


@router.get("/{arquivo_id}/baixar")
def baixar(automation_id: int, arquivo_id: str, db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> Response:
    ensure_automation_grant(db, user, automation_id, VER_TELAS_E_LOGS)
    linha = db.execute(_da_automacao(automation_id).where(ArtifactRecord.id == arquivo_id)).first()
    if linha is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado nesta automação.")
    artefato = linha[0]
    if artefato.status == "deleted":
        raise HTTPException(status_code=410, detail="Arquivo apagado pela retenção.")
    if artefato.status != "available" or not artefato.stored_object_id:
        raise HTTPException(status_code=409, detail="Arquivo ainda não disponível.")
    storage = build_storage_adapters(db)
    try:
        conteudo, tipo = LerObjeto(storage.object_storage, storage.stored_objects).execute(artefato.stored_object_id)
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.") from exc
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(user, "id", "")) or None,
        action="automacao.arquivo.baixado", resource_type="artifact", resource_id=artefato.id,
        metadata={"automation_id": automation_id, "execucao_id": artefato.execution_id, "nome": artefato.name},
        occurred_at=datetime.now(UTC)))
    db.commit()
    ascii_nome = artefato.name.encode("ascii", "replace").decode().replace('"', "_").replace("?", "_")
    return Response(content=conteudo, media_type=tipo or "application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename=\"{ascii_nome}\"; filename*=UTF-8''{quote(artefato.name)}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
