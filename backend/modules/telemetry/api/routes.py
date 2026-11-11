from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db, get_session_factory
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.orchestration.application.use_cases import GetExecutionDetails
from modules.orchestration.domain.errors import OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.telemetry.application.dto import to_payload
from modules.telemetry.application.use_cases import (
    GetExecutionEvents,
    GetExecutionLogs,
    GetExecutionMetrics,
    GetExecutionProcesses,
    GetExecutionProgress,
    GetExecutionTimeline,
)
from modules.telemetry.application.use_cases.estimates import GetExecutionEstimate, GetItemStepTimes
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.repositories.sqlalchemy_steps import (
    SqlAlchemyExecutionJobsReader,
    latest_manifest_for_automation,
)

router = APIRouter(prefix="/executions")


@router.get("/{execution_id}/events")
def get_execution_events(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = None,
    event_type: str | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    page = GetExecutionEvents(adapters.events).execute(
        execution_id,
        limit=limit,
        cursor=cursor,
        event_type=event_type,
        level=level,
    )
    return to_payload(page)


@router.get("/{execution_id}/timeline")
def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    limit: int = Query(default=300, ge=1, le=1000),
    cursor: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionTimeline(adapters.events).execute(execution_id, limit=limit, cursor=cursor))


@router.get("/{execution_id}/logs")
def get_execution_logs(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionLogs(adapters.events).execute(execution_id, limit=limit, cursor=cursor, level=level))


@router.get("/{execution_id}/metrics")
def get_execution_metrics(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=1000),
    metric_name: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionMetrics(adapters.metrics).execute(execution_id, limit=limit, metric_name=metric_name))


@router.get("/{execution_id}/progress")
def get_execution_progress(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionProgress(adapters.events).execute(execution_id))


@router.get("/{execution_id}/processes")
def get_execution_processes(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionProcesses(adapters.events).execute(execution_id))


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    fabrica: Any = Depends(get_session_factory),
) -> StreamingResponse:
    """Eventos ao vivo de uma execução (SSE).

    O token vai no cabeçalho ``Authorization`` (nunca na URL). Avisos chegam por
    ``LISTEN/NOTIFY`` e cada aviso relê o banco a partir do último evento enviado, então
    funciona com vários processos e nada se perde numa reconexão (``Last-Event-ID``).
    Logs e passos só vão para quem tem ``ver_telas_e_logs`` na automação.
    """
    from modules.access.api.authorization import acesso_por_automacao
    from modules.access.domain.concessao import VER_TELAS_E_LOGS
    from modules.telemetry.api.acompanhar import usuario_do_cabecalho
    from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, esperar_aviso, ouvinte
    from modules.telemetry.infrastructure.repositories.sqlalchemy_images import SqlAlchemyStepImageRepository

    with fabrica() as db:
        user = usuario_do_cabecalho(db, request)
        details = _ensure_execution_view(db, user, execution_id)
        from modules.telemetry.api.acompanhar import _automation_id
        automation_id = _automation_id(details, db)
        pode_logs = automation_id is not None and acesso_por_automacao(db).pode(user, automation_id, VER_TELAS_E_LOGS)
        cursor = last_event_id or SqlAlchemyStepImageRepository(db).ultimo_evento(execution_id)

    def ler(desde: str | None) -> tuple[list[Any], Any]:
        with fabrica() as sessao:
            adapters = build_telemetry_adapters(sessao)
            if desde:
                novos = adapters.events.list_events_after_id(execution_id, desde, limit=500)
            else:
                novos, _ = adapters.events.list_events(execution_id, limit=500)
            return novos, GetExecutionProgress(adapters.events).execute(execution_id)

    async def event_stream():
        nonlocal cursor
        async with ouvinte.assinar(CANAL_EXECUCAO, execution_id) as sinal:
            primeira = True
            while not await request.is_disconnected():
                if not primeira:
                    chegou = await esperar_aviso(sinal, 15.0)
                    if not chegou and ouvinte.conectado:
                        yield ": keepalive\n\n"
                        continue
                novos, progresso = await asyncio.to_thread(ler, cursor)
                for evento in novos:
                    cursor = evento.id
                    if pode_logs or not _evento_de_tela_ou_log(evento):
                        yield _sse("execution.event", {"type": "execution.event", "event": to_payload(evento)}, event_id=evento.id)
                yield _sse("execution.progress", {"type": "execution.progress", "progress": to_payload(progresso)})
                primeira = False

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


def _evento_de_tela_ou_log(evento: Any) -> bool:
    if evento.event_type in {"log", "warning", "error"}:
        return True
    tipo = (evento.payload or {}).get("type") if evento.event_type == "automation.event" else None
    return tipo in {"log", "passo", "espera.atualizada", "atencao"}


def _ensure_execution_view(db: Session, user: Any, execution_id: str):
    adapters = build_orchestration_adapters(db)
    try:
        details = GetExecutionDetails(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.offers,
            adapters.automation_versions,
            adapters.agent_selection,
        ).execute(execution_id)
    except OrchestrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if details.automation_version is not None:
        ensure_automation_action(db, user, details.automation_version.automation_id, "can_view")
    return details


def _sse(event: str, payload: dict[str, Any], event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False, default=str)}")
    return "\n".join(lines) + "\n\n"


@router.get("/{execution_id}/estimativa")
def get_execution_estimate(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Estimativa por etapa, item, job e execução, com o tempo real ao lado e a base de cada número."""
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return GetExecutionEstimate(SqlAlchemyExecutionJobsReader(db), adapters.manifests, adapters.steps, adapters.items).execute(execution_id)


automation_times_router = APIRouter(prefix="/automations")


@automation_times_router.get("/{automation_id}/tempos")
def get_item_step_times(
    automation_id: int,
    item: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Tempo por etapa de UM item: execuções, típico, por tarefa, último e quando."""
    ensure_automation_action(db, user, automation_id, "can_view")
    manifesto = latest_manifest_for_automation(db, automation_id)
    if manifesto is None:
        raise HTTPException(status_code=404, detail="Automação sem versão com etapas declaradas.")
    adapters = build_telemetry_adapters(db)
    return {"automation_id": automation_id, "item": item,
            "etapas": GetItemStepTimes(adapters.steps).execute(automation_id, item, manifesto.steps)}
