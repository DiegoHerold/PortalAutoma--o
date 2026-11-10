"""API da fila: ver, pedir execução, reordenar, cancelar, decidir job perdido e despachar."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db, get_session_factory
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.dispatch.application.use_cases.queue import TEXTOS
from modules.dispatch.infrastructure.adapters.fila import build_fila
from modules.orchestration.application.use_cases.queue import FilaError
from modules.telemetry.infrastructure.realtime.postgres import CANAL_FILA, notificar

router = APIRouter(prefix="/fila", tags=["fila"])


def _agora() -> datetime:
    return datetime.now(UTC)


def _pode(db: Session, user: Any, automation_id: int | None, acao: str) -> bool:
    if automation_id is None:
        return False
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_automation_action(user, automation_id, acao)
        return True
    except (AuthorizationDenied, Exception):  # noqa: BLE001 - sem permissão ou automação inexistente: não mostra
        return False


def _admin(user: Any) -> bool:
    return getattr(getattr(user, "role", None), "slug", getattr(user, "role", None)) == "admin"


def _mudou() -> None:
    notificar(CANAL_FILA)


def _job_da_fila(db: Session, fila: Any, job_id: str, user: Any, acao: str) -> Any:
    tarefa = fila.tasks.get(job_id)
    if tarefa is None or tarefa.enqueue_batch_id is None:
        raise HTTPException(status_code=404, detail="Job não encontrado na fila.")
    ensure_automation_action(db, user, fila.reader.automation_id(tarefa.automation_version_id), acao)
    return tarefa


@router.get("")
def ver_fila(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Jobs esperando, na ordem: posição, máquina prevista, início e término previstos e por que esperam."""
    visao = build_fila(db).ver.execute(_agora())
    visao["jobs"] = [j for j in visao["jobs"] if _pode(db, user, j["automation_id"], "can_view")]
    visao["perdidos"] = [j for j in visao["perdidos"] if _pode(db, user, j["automation_id"], "can_view")]
    for job in visao["jobs"]:
        for motivo in job["motivos"]:
            outra = motivo.pop("automation_id", None)
            if outra is not None and not _admin(user) and not _pode(db, user, outra, "can_view"):
                motivo["texto"] = TEXTOS.get(motivo["codigo"], motivo["codigo"])  # sem o nome da automação alheia
    if not _admin(user):
        # A ocupação da máquina explica a espera; qual job a ocupa só o admin vê.
        for maquina in visao["maquinas"]:
            maquina["rodando"] = [{**r, "job_id": None} for r in maquina["rodando"]]
    return visao


@router.post("/execucoes", status_code=201)
def pedir_execucao(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                   user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Um job por grupo de itens. Pedido igual já na fila ou rodando aponta para o job existente."""
    fila = build_fila(db)
    versao = corpo.get("automation_version_id")
    if not isinstance(versao, int):
        raise HTTPException(status_code=422, detail="Informe automation_version_id.")
    ensure_automation_action(db, user, fila.reader.automation_id(versao) or 0, "can_execute")
    itens = corpo.get("itens") or []
    if not isinstance(itens, list) or len(itens) > 2000 or not all(isinstance(i, dict) for i in itens):
        raise HTTPException(status_code=422, detail="itens deve ser uma lista de até 2000 objetos.")
    try:
        resultado = fila.enfileirar.execute(
            automation_version_id=versao, itens=itens, parametros=corpo.get("parametros") or {},
            prioridade=int(corpo.get("prioridade") or 0), solicitante=str(getattr(user, "id", "") or ""), now=_agora())
    except FilaError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fila.transaction.commit()
    _mudou()
    return resultado


@router.patch("/jobs/{job_id}")
def reordenar(job_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
              user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Prioridade e posição manual, só para job que ainda não começou."""
    fila = build_fila(db)
    tarefa = _job_da_fila(db, fila, job_id, user, "can_execute")
    if tarefa.status != "queued":
        raise HTTPException(status_code=409, detail="Só dá para reordenar job que ainda não começou.")
    mudancas: dict[str, Any] = {}
    if "prioridade" in corpo:
        mudancas["priority"] = int(corpo["prioridade"])
    if "posicao_manual" in corpo:
        valor = corpo["posicao_manual"]
        mudancas["manual_position"] = None if valor is None else int(valor)
    fila.tasks.save(replace(tarefa, **mudancas))
    fila.transaction.commit()
    _mudou()
    return {"job_id": job_id, "prioridade": mudancas.get("priority", tarefa.priority),
            "posicao_manual": mudancas.get("manual_position", tarefa.manual_position)}


@router.post("/jobs/{job_id}/cancelar")
def cancelar(job_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    fila = build_fila(db)
    tarefa = _job_da_fila(db, fila, job_id, user, "can_execute")
    if tarefa.status != "queued":
        raise HTTPException(status_code=409, detail="Só dá para cancelar pela fila um job que ainda não começou.")
    fila.tasks.save(replace(tarefa, status="cancelled", completed_at=_agora(), failure_summary="Cancelado na fila."))
    fila.transaction.commit()
    _mudou()
    return {"job_id": job_id, "status": "cancelled"}


@router.post("/jobs/{job_id}/decisao")
def decidir_perdido(job_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                    user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Job perdido: ``continuar`` (mesma máquina, salvo estado central) ou ``recomecar`` (do zero)."""
    fila = build_fila(db)
    tarefa = _job_da_fila(db, fila, job_id, user, "can_execute")
    execucao = (tarefa.retry_policy or {})
    try:
        nova = fila.decidir_perdido.execute(job_id=job_id, decisao=str(corpo.get("decisao") or ""),
                                            estado_central=bool(execucao.get("central_state", False)), now=_agora())
    except FilaError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    fila.transaction.commit()
    _mudou()
    return {"job_id": job_id, "status": nova.status, "maquina_obrigatoria": nova.required_machine_id}


@router.post("/despachar")
def despachar(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """O mesmo ciclo que o Celery roda: marca perdidos e entrega os jobs às máquinas livres."""
    if not _admin(user):
        raise HTTPException(status_code=403, detail="Só administradores disparam o despacho manualmente.")
    return despachar_agora(db)


def despachar_agora(db: Session) -> dict[str, Any]:
    fila = build_fila(db)
    agora = _agora()
    perdidos = fila.marcar_perdidos.execute(agora)
    fila.transaction.commit()
    entregues = fila.despachar.execute(agora)
    if perdidos or entregues:
        _mudou()
    return {"perdidos": perdidos, "entregues": entregues}


@router.get("/avisos")
def avisos(request: Request, fabrica: Any = Depends(get_session_factory)) -> StreamingResponse:
    """SSE: "mudou" quando a fila muda. Token só no cabeçalho ``Authorization``."""
    from modules.telemetry.api.acompanhar import fluxo_de_avisos, usuario_do_cabecalho

    with fabrica() as db:
        usuario_do_cabecalho(db, request)
    return fluxo_de_avisos(request, CANAL_FILA, "")
