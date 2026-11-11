"""API de "Acompanhar uma execução" (Fase 4).

- ``GET /execucoes/{id}/acompanhar``: o agora (etapa, item, progresso, tela atual com
  "N s nesta tela", passos), decorrido, falta e término previsto, e as etapas com
  estimativa e tempo real. Precisa de ``ver_execucoes``; tela e passos só com
  ``ver_telas_e_logs``.
- ``GET /execucoes/{id}/logs``: log ao vivo (``ver_telas_e_logs``).
- ``GET /execucoes/{id}/imagens/{imagem_id}?tamanho=``: a imagem, servida aqui depois da
  permissão. Nunca há URL pública. Ver é auditado.
- ``GET /execucoes/{id}/avisos``: SSE que só avisa "mudou"; a tela busca o resto. O token
  vai no cabeçalho ``Authorization``, nunca na URL.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db, get_session_factory
from modules.access.api.authorization import acesso_por_automacao, ensure_automation_grant
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import AuthenticateToken
from modules.access.domain import AuthenticationFailed
from modules.access.domain.concessao import CONTROLAR, VER_EXECUCOES, VER_TELAS_E_LOGS
from modules.access.infrastructure.adapters import build_access_adapters
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.orchestration.application.use_cases import GetExecutionDetails
from modules.orchestration.domain.errors import OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.storage.application.use_cases.objetos import LerObjeto
from modules.storage.domain.errors import ArtifactNotFound
from modules.storage.infrastructure.adapters import build_storage_adapters
from modules.telemetry.application.use_cases.estimates import GetExecutionEstimate, QueueEstimates
from modules.telemetry.domain.acompanhamento import estado
from modules.telemetry.domain.imagens import TAMANHOS
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, esperar_aviso, ouvinte
from modules.telemetry.infrastructure.repositories.sqlalchemy_images import SqlAlchemyStepImageRepository
from modules.telemetry.infrastructure.repositories.sqlalchemy_steps import SqlAlchemyExecutionJobsReader

router = APIRouter(prefix="/execucoes", tags=["acompanhar"])

FINAIS = {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "lost"}
INTERVALO_AVISO_S = 15.0
AUDITORIA_MINIATURAS_S = 600


def _agora() -> datetime:
    return datetime.now(UTC)


def _detalhes(db: Session, execution_id: str) -> Any:
    o = build_orchestration_adapters(db)
    try:
        return GetExecutionDetails(o.executions, o.tasks, o.attempts, o.offers, o.automation_versions,
                                   o.agent_selection).execute(execution_id)
    except OrchestrationError as exc:
        raise HTTPException(status_code=404, detail="Execução não encontrada.") from exc


def _automation_id(detalhes: Any, db: Session | None = None) -> int | None:
    """Da versão da execução; sem o snapshot da versão, pela tarefa (catálogo, só leitura)."""
    versao = getattr(detalhes, "automation_version", None)
    if getattr(versao, "automation_id", None) is not None:
        return versao.automation_id
    if db is None or not detalhes.tasks:
        return None
    return SqlAlchemyStepImageRepository(db).automation_id_da_tarefa(detalhes.tasks[0].id)


def _auditar(db: Session, user: Any, acao: str, execution_id: str, metadados: dict[str, Any]) -> None:
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(user, "id", "")) or None, action=acao,
        resource_type="execution", resource_id=execution_id, metadata=metadados, occurred_at=_agora()))
    db.commit()


def _falta(db: Session, execution_id: str, tarefa: Any, tentativa: Any, agora: datetime) -> tuple[float | None, str | None]:
    if tentativa is None:
        return None, "aguardando_job_sem_previsao"
    t = build_telemetry_adapters(db)
    estimativas = QueueEstimates(t.steps, t.manifests, t.items.plans, lambda _job: tentativa.id)
    return estimativas.restante(execution_id, tarefa.id, tentativa.started_at or tentativa.created_at, agora)


@router.get("/{execution_id}/acompanhar")
def acompanhar(execution_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    detalhes = _detalhes(db, execution_id)
    automation_id = _automation_id(detalhes, db)
    ensure_automation_grant(db, user, automation_id, VER_EXECUCOES)
    acesso = acesso_por_automacao(db)
    pode_telas = acesso.pode(user, automation_id, VER_TELAS_E_LOGS)
    imagens = SqlAlchemyStepImageRepository(db)
    agora = _agora()
    execucao = detalhes.execution
    rodando = any(t.status == "running" for t in detalhes.tasks)

    ultima_por_tarefa: dict[str, Any] = {}
    for tentativa in sorted(detalhes.attempts, key=lambda a: a.attempt_number):
        ultima_por_tarefa[tentativa.task_execution_id] = tentativa
    jobs = []
    for tarefa in detalhes.tasks:
        tentativa = ultima_por_tarefa.get(tarefa.id)
        maquina_id, maquina_nome = imagens.nome_da_maquina(getattr(tentativa, "machine_id", None),
                                                           getattr(tentativa, "agent_id", None)) if tentativa else (None, None)
        falta_s, motivo = _falta(db, execution_id, tarefa, tentativa, agora) if tarefa.status == "running" else (None, None)
        jobs.append({
            "job_id": tarefa.id, "status": tarefa.status, "pool": tarefa.pool, "itens": (tarefa.input or {}).get("itens") or [],
            "maquina_id": maquina_id, "maquina_nome": maquina_nome,
            "modo": getattr(tentativa, "executor_type", None), "tentativa": getattr(tentativa, "attempt_number", None),
            "desde": (tentativa.started_at or tentativa.created_at).isoformat() if tentativa else None,
            "falta_s": falta_s, "motivo_sem_previsao": motivo,
            "termino_previsto": (agora.timestamp() + falta_s) if falta_s is not None else None,
            "falha": tarefa.failure_summary,
        })
    for job in jobs:
        if job["termino_previsto"] is not None:
            job["termino_previsto"] = datetime.fromtimestamp(job["termino_previsto"], UTC).isoformat()

    agora_da_tela = estado(imagens.eventos_de_estado(execution_id), agora, rodando=rodando)
    if pode_telas:
        situacoes = imagens.situacoes(execution_id)
        for passo in agora_da_tela["passos"]:
            passo["imagem"] = situacoes.get(passo["imagem_id"]) if passo["imagem_id"] else None
        if agora_da_tela["tela"]:
            agora_da_tela["tela"]["imagem"] = situacoes.get(agora_da_tela["tela"]["imagem_id"])
    else:
        agora_da_tela["tela"], agora_da_tela["passos"] = None, []

    inicio = execucao.started_at or execucao.created_at
    fim = execucao.completed_at if execucao.status in FINAIS else None
    rodando_jobs = [j for j in jobs if j["status"] == "running"]
    falta_total = (max(j["falta_s"] for j in rodando_jobs)
                   if rodando_jobs and all(j["falta_s"] is not None for j in rodando_jobs) else None)
    t = build_telemetry_adapters(db)
    return {
        "gerado_em": agora.isoformat(),
        "execucao": {"id": execucao.id, "status": execucao.status, "criada_em": execucao.created_at.isoformat(),
                     "iniciada_em": execucao.started_at.isoformat() if execucao.started_at else None,
                     "concluida_em": execucao.completed_at.isoformat() if execucao.completed_at else None,
                     "falha": execucao.failure_summary, "solicitante": execucao.requested_by},
        "automacao": {"id": automation_id, "nome": getattr(detalhes.automation_version, "automation_name", None),
                      "versao": getattr(detalhes.automation_version, "version", None)},
        "pode": {"ver_telas_e_logs": pode_telas, "controlar": acesso.pode(user, automation_id, CONTROLAR)},
        "rodando": rodando,
        "decorrido_s": max(((fim or agora) - inicio).total_seconds(), 0.0) if inicio else None,
        "falta_s": falta_total,
        "termino_previsto": datetime.fromtimestamp(agora.timestamp() + falta_total, UTC).isoformat()
        if falta_total is not None else None,
        "jobs": jobs,
        "agora": agora_da_tela,
        "estimativa": GetExecutionEstimate(SqlAlchemyExecutionJobsReader(db), t.manifests, t.steps, t.items).execute(execution_id),
    }


@router.get("/{execution_id}/logs")
def logs(execution_id: str, depois: str | None = Query(default=None, max_length=80),
         limite: int = Query(default=200, ge=1, le=500), esconder_espera: bool = Query(default=True),
         db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    ensure_automation_grant(db, user, _automation_id(_detalhes(db, execution_id), db), VER_TELAS_E_LOGS)
    imagens = SqlAlchemyStepImageRepository(db)
    posicao = imagens.posicao(depois) if depois else None
    if depois and posicao is None:
        raise HTTPException(status_code=400, detail="Cursor desconhecido.")
    linhas, cursor = imagens.logs(execution_id, depois_de=posicao, limite=limite, esconder_espera=esconder_espera)
    return {"logs": linhas, "cursor": cursor or depois}


_vistas: dict[tuple[str, str], float] = {}
_trava_vistas = threading.Lock()


def _primeira_vista(user_id: str, execution_id: str) -> bool:
    """Miniaturas e telas médias: um registro por pessoa e execução a cada 10 minutos."""
    agora = time.monotonic()
    with _trava_vistas:
        anterior = _vistas.get((user_id, execution_id))
        if anterior is not None and agora - anterior < AUDITORIA_MINIATURAS_S:
            return False
        _vistas[(user_id, execution_id)] = agora
        return True


@router.get("/{execution_id}/imagens/{imagem_id}")
def imagem(execution_id: str, imagem_id: str, tamanho: str = Query(default="media"),
           db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Response:
    if tamanho not in TAMANHOS:
        raise HTTPException(status_code=422, detail=f"tamanho: {', '.join(TAMANHOS)}.")
    ensure_automation_grant(db, user, _automation_id(_detalhes(db, execution_id), db), VER_TELAS_E_LOGS)
    registro = SqlAlchemyStepImageRepository(db).da_execucao(execution_id, imagem_id)
    if registro is not None and registro.apagada_em is not None:
        raise HTTPException(status_code=410, detail="Imagem apagada pela retenção.")
    objeto = getattr(registro, f"{tamanho}_id", None) if registro else None
    if objeto is None:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    storage = build_storage_adapters(db)
    try:
        conteudo, tipo = LerObjeto(storage.object_storage, storage.stored_objects).execute(objeto)
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.") from exc
    if tamanho == "cheia":
        _auditar(db, user, "execucao.tela.ampliada", execution_id, {"imagem_id": imagem_id})
    elif _primeira_vista(str(getattr(user, "id", "")), execution_id):
        _auditar(db, user, "execucao.telas.vistas", execution_id, {"imagem_id": imagem_id, "tamanho": tamanho})
    # A imagem não muda; o navegador guarda só para esta pessoa (nunca cache compartilhado).
    return Response(content=conteudo, media_type=tipo,
                    headers={"Cache-Control": "private, max-age=3600, immutable", "X-Content-Type-Options": "nosniff"})


def usuario_do_cabecalho(db: Session, request: Request) -> Any:
    """Token só no cabeçalho ``Authorization`` (regra: credencial nunca na URL)."""
    autorizacao = request.headers.get("authorization") or ""
    if not autorizacao.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Envie o token no cabeçalho Authorization.")
    try:
        adapters = build_access_adapters(db)
        return AuthenticateToken(adapters.access, adapters.tokens).execute(autorizacao[7:].strip())
    except (AuthenticationFailed, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Token inválido.") from exc


def fluxo_de_avisos(request: Request, canal: str, chave: str) -> StreamingResponse:
    """SSE de avisos: "mudou" quando há novidade; sem conexão de escuta, avisa a cada 15 s."""

    async def gerar():
        async with ouvinte.assinar(canal, chave) as sinal:
            yield "retry: 3000\nevent: pronto\ndata: {}\n\n"
            while not await request.is_disconnected():
                chegou = await esperar_aviso(sinal, INTERVALO_AVISO_S)
                if chegou or not ouvinte.conectado:
                    yield f"event: mudou\ndata: {json.dumps({'chave': chave, 'em': _agora().isoformat()})}\n\n"
                else:
                    yield ": ainda aqui\n\n"

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get("/{execution_id}/avisos")
def avisos(execution_id: str, request: Request, fabrica: Any = Depends(get_session_factory)) -> StreamingResponse:
    # Sessão curta só para autenticar e checar a permissão: o stream não segura conexão do banco.
    with fabrica() as db:
        user = usuario_do_cabecalho(db, request)
        ensure_automation_grant(db, user, _automation_id(_detalhes(db, execution_id), db), VER_EXECUCOES)
    return fluxo_de_avisos(request, CANAL_EXECUCAO, execution_id)
