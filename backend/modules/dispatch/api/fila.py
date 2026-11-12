"""API da fila: ver, pedir execução, reordenar, cancelar, decidir job perdido e despachar."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db, get_session_factory
from modules.access.api.authorization import ensure_automation_action, precisa
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.dispatch.application.use_cases.queue import TEXTOS
from modules.dispatch.infrastructure.adapters.fila import build_continuar, build_encerrar, build_fila, build_parar
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


@router.get("", dependencies=[Depends(precisa("fila.ver", "automacoes.ver"))])
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


@router.patch("/jobs/{job_id}", dependencies=[Depends(precisa("fila.gerenciar"))])
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


@router.post("/jobs/{job_id}/cancelar", dependencies=[Depends(precisa("fila.gerenciar"))])
def cancelar(job_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    fila = build_fila(db)
    tarefa = _job_da_fila(db, fila, job_id, user, "can_execute")
    if tarefa.status != "queued":
        raise HTTPException(status_code=409, detail="Só dá para cancelar pela fila um job que ainda não começou.")
    from modules.orchestration.application.use_cases.queue import fechar_execucao
    from modules.orchestration.infrastructure.adapters import build_orchestration_adapters

    fila.tasks.save(replace(tarefa, status="cancelled", completed_at=_agora(), failure_summary="Cancelado na fila."))
    fechar_execucao(build_orchestration_adapters(db).executions, fila.tasks, tarefa.execution_id, _agora())
    fila.transaction.commit()
    _mudou()
    return {"job_id": job_id, "status": "cancelled"}


def _automacao_da_execucao(db: Session, fila: Any, execution_id: str) -> int:
    tarefas = fila.tasks.list_for_execution(execution_id)
    if not tarefas or tarefas[0].enqueue_batch_id is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada na fila.")
    automation_id = fila.reader.automation_id(tarefas[0].automation_version_id)
    if automation_id is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada na fila.")
    return automation_id


def _auditar(db: Session, user: Any, acao: str, execution_id: str, depois: dict[str, Any]) -> None:
    from uuid import uuid4

    from modules.governance.domain.audit import AuditEvent
    from modules.governance.infrastructure.adapters import build_governance_adapters

    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(user, "id", "") or "") or None, action=acao,
        resource_type="execution", resource_id=execution_id, before=None, after=depois, occurred_at=_agora()))


@router.post("/execucoes/{execution_id}/parar")
def parar_execucao(execution_id: str, request: Request, corpo: dict[str, Any] = Body(default={}),
                   db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``modo``: ``apos_item`` (termina o item atual e não começa outro) ou ``agora``. Pede a
    concessão ``controlar`` ("Parar e retomar execuções")."""
    from modules.access.api.authorization import ensure_automation_grant
    from modules.access.domain.concessao import CONTROLAR

    fila = build_fila(db)
    ensure_automation_grant(db, user, _automacao_da_execucao(db, fila, execution_id), CONTROLAR)
    motivo = str(corpo.get("motivo") or "").strip()[:300] or None

    def cancelar_no_agent(execucao: str, razao: str | None) -> object:
        from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
        from modules.orchestration.api.routes import _actor
        from modules.orchestration.application.use_cases.resilience import RequestExecutionCancellation

        d = build_dispatch_adapters(db)
        return RequestExecutionCancellation(d.executions, d.tasks, d.attempts, d.cancellation_requests, d.commands,
                                            d.reservations, d.locks, d.leases, d.outbox, d.transaction
                                            ).execute(execucao, actor=_actor(user, request), reason=razao or "parada pedida no Portal")

    try:
        resultado = build_parar(db, cancelar_no_agent).execute(
            execution_id=execution_id, modo=str(corpo.get("modo") or ""), motivo=motivo, now=_agora())
    except FilaError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _auditar(db, user, "execucao.parada_pedida", execution_id, {"modo": resultado["modo"], "motivo": motivo,
             "canceladas_na_fila": resultado["canceladas_na_fila"], "avisadas": resultado["avisadas"]})
    db.commit()
    _mudou()
    from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, notificar as avisar

    avisar(CANAL_EXECUCAO, execution_id)
    return resultado


@router.post("/execucoes/{execution_id}/encerrar")
def encerrar_no_portal(execution_id: str, db: Session = Depends(get_db),
                       user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """O cancelamento foi pedido e a automação não respondeu em 2 min: encerra no Portal (job
    cancelado com erro, máquina liberada, token revogado). O processo pode seguir aberto na
    máquina; o SDK 0.4.0 se encerra sozinho quando o Portal recusa o token."""
    from modules.access.api.authorization import ensure_automation_grant
    from modules.access.domain.concessao import CONTROLAR
    from modules.dispatch.domain.comunicacao import PRAZO_DO_CANCELAMENTO
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore

    fila = build_fila(db)
    ensure_automation_grant(db, user, _automacao_da_execucao(db, fila, execution_id), CONTROLAR)
    agora = _agora()
    ativas = [t for t in fila.tasks.list_for_execution(execution_id) if t.status in ("running", "cancelling")]
    tentativas = [a for a in (fila.store.last_attempt(t.id) for t in ativas) if a is not None and a.executor_type == "direct"]
    paradas = SqlAlchemyDirectCommandStore(db).paradas_pedidas([a.id for a in tentativas])
    vencidas = [a for a in tentativas if (paradas.get(a.id) or {}).get("tipo") == "cancelar"
                and agora - paradas[a.id]["pedido_em"] >= PRAZO_DO_CANCELAMENTO]
    if not vencidas:
        raise HTTPException(status_code=409, detail="Só dá para encerrar no Portal depois de 2 min de cancelamento sem resposta.")
    encerrar = build_encerrar(db)
    for tentativa in vencidas:
        recebido = bool(paradas[tentativa.id].get("recebido_em"))
        encerrar.execute(attempt_id=tentativa.id, codigo="CANCEL_NOT_CONFIRMED", now=agora, motivo=(
            "Encerrada no Portal: a automação recebeu o cancelamento e não parou em 2 min." if recebido
            else "Encerrada no Portal: a automação não recebeu o cancelamento em 2 min."))
    _auditar(db, user, "execucao.encerrada_no_portal", execution_id, {"tentativas": [a.id for a in vencidas]})
    db.commit()
    _mudou()
    return {"execution_id": execution_id, "encerradas": len(vencidas)}


@router.get("/execucoes/{execution_id}/continuar")
def previa_de_continuar(execution_id: str, db: Session = Depends(get_db),
                        user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """O que rodaria de novo: os itens que não deram certo. Os outros são pulados."""
    from modules.access.api.authorization import ensure_automation_grant
    from modules.access.domain.concessao import VER_EXECUCOES

    fila = build_fila(db)
    ensure_automation_grant(db, user, _automacao_da_execucao(db, fila, execution_id), VER_EXECUCOES)
    try:
        return build_continuar(db).previa(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/execucoes/{execution_id}/continuar", status_code=201)
def continuar_execucao(execution_id: str, db: Session = Depends(get_db),
                       user: Any = Depends(get_current_user)) -> dict[str, Any]:
    from modules.access.api.authorization import ensure_automation_grant
    from modules.access.domain.concessao import CONTROLAR

    fila = build_fila(db)
    ensure_automation_grant(db, user, _automacao_da_execucao(db, fila, execution_id), CONTROLAR)
    try:
        resultado = build_continuar(db).execute(execution_id=execution_id, solicitante=str(getattr(user, "id", "") or ""),
                                               now=_agora())
    except FilaError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _auditar(db, user, "execucao.continuada", execution_id, {"nova_execucao": resultado.get("execution_id"),
             "itens": resultado["itens"], "pulados": resultado["pulados"]})
    db.commit()
    _mudou()
    return resultado


@router.post("/jobs/{job_id}/decisao", dependencies=[Depends(precisa("fila.gerenciar"))])
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
