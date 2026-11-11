"""API do modo direto (contracts/automation-events/v1/README.md, seção "Modo direto").

Traduz HTTP para os mesmos casos de uso do Telemetry que o Agent usa: os eventos, o
histórico e as estimativas saem iguais nos dois modos. Toda recusa de credencial é
auditada. O token do job vem no cabeçalho, nunca na URL.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.dispatch.application.use_cases.job_tokens import AuthenticateJobToken, JobTokenGrant, JobTokenRejected
from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore, SqlAlchemyJobTokenStore
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.telemetry.application.dto import EventBatchCommand
from modules.telemetry.application.use_cases import IngestExecutionEventBatch
from modules.telemetry.domain.errors import ExecutionAttemptTelemetryError, TelemetryValidationError
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.adapters.automation_events import validate_automation_event

router = APIRouter(prefix="/direto/jobs", tags=["modo-direto"])

LIMITE_CORPO = 1_000_000
LIMITE_EVENTOS = 500


def _erro(codigo: int, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"erro": mensagem})


def _auditar(db: Session, request: Request, *, acao: str, job_id: str, metadados: dict[str, Any]) -> None:
    """Em transação própria: a recusa fica registrada mesmo sem nada gravado no pedido."""
    try:
        build_governance_adapters(db).audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="direct_instance", actor_id=metadados.get("instancia"),
            action=acao, resource_type="job", resource_id=job_id, metadata=metadados,
            ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"),
            occurred_at=datetime.now(UTC),
        ))
        db.commit()
    except Exception:  # noqa: BLE001 - auditoria não pode derrubar a resposta de recusa
        db.rollback()


def _autenticar(db: Session, request: Request, job_id: str) -> JobTokenGrant | JSONResponse:
    autorizacao = request.headers.get("authorization") or ""
    token = autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else None
    try:
        grant = AuthenticateJobToken(SqlAlchemyJobTokenStore(db)).execute(job_id=job_id, token=token, now=datetime.now(UTC))
        SqlAlchemyJobTokenStore(db).touch_instance(grant.direct_instance_id, datetime.now(UTC))
        db.commit()
        return grant
    except JobTokenRejected as exc:
        db.rollback()
        _auditar(db, request, acao="direto.credencial_recusada", job_id=job_id, metadados={"motivo": exc.motivo})
        return _erro(401, "token do job inválido para este job")


async def _corpo_json(request: Request) -> dict[str, Any] | JSONResponse:
    if not (request.headers.get("content-type") or "").startswith("application/json"):
        return _erro(415, "envie Content-Type: application/json")
    tamanho = int(request.headers.get("content-length") or 0)
    if tamanho > LIMITE_CORPO:
        return _erro(413, f"corpo acima de {LIMITE_CORPO} bytes")
    corpo = b""
    async for parte in request.stream():
        corpo += parte
        if len(corpo) > LIMITE_CORPO:  # Content-Length mentiroso não passa
            return _erro(413, f"corpo acima de {LIMITE_CORPO} bytes")
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        return _erro(400, "JSON inválido")
    return dados if isinstance(dados, dict) else _erro(400, "esperado um objeto JSON")


@router.put("/{job_id}/imagens/{imagem_id}", status_code=201)
async def receber_imagem(job_id: str, imagem_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    """Imagem do passo (``image/jpeg``). Só por HTTPS, só deste job; nunca pelo evento."""
    from modules.telemetry.domain.imagens import ImagemInvalida
    from modules.telemetry.infrastructure.adapters.factory import build_registrar_imagem
    from modules.telemetry.infrastructure.imagens import LIMITE_BYTES

    grant = _autenticar(db, request, job_id)
    if isinstance(grant, JSONResponse):
        return grant
    if (request.headers.get("content-type") or "").split(";")[0].strip().lower() != "image/jpeg":
        return _erro(415, "envie Content-Type: image/jpeg")
    if int(request.headers.get("content-length") or 0) > LIMITE_BYTES:
        return _erro(413, f"imagem acima de {LIMITE_BYTES} bytes")
    conteudo = b""
    async for parte in request.stream():
        conteudo += parte
        if len(conteudo) > LIMITE_BYTES:
            return _erro(413, f"imagem acima de {LIMITE_BYTES} bytes")
    try:
        resultado = build_registrar_imagem(db).execute(attempt_id=grant.execution_attempt_id, imagem_id=imagem_id,
                                                        conteudo=conteudo, origem="direto")
    except ImagemInvalida as exc:
        db.rollback()
        return _erro(exc.status, exc.motivo)
    return JSONResponse(status_code=201, content={"imagem_id": resultado["imagem_id"]})


LIMITE_ARQUIVO = 100 * 1024 * 1024


@router.put("/{job_id}/arquivos", status_code=201)
async def receber_arquivo(job_id: str, request: Request, nome: str = Query(..., min_length=1, max_length=255),
                          item: str | None = Query(default=None, max_length=120), db: Session = Depends(get_db)) -> Any:
    """Arquivo entregue pela automação (planilha, TXT...), até 100 MB: vira artefato da execução (Fase 8).
    Só deste job, pelo token no cabeçalho; os bytes nunca passam pelos eventos."""
    import hashlib
    import tempfile
    from pathlib import Path

    from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord
    from modules.storage.application.use_cases.objetos import GuardarArquivoEntregue
    from modules.storage.infrastructure.adapters import build_storage_adapters

    grant = _autenticar(db, request, job_id)
    if isinstance(grant, JSONResponse):
        return grant
    if int(request.headers.get("content-length") or 0) > LIMITE_ARQUIVO:
        return _erro(413, f"arquivo acima de {LIMITE_ARQUIVO} bytes")
    tipo = (request.headers.get("content-type") or "application/octet-stream").split(";")[0].strip()[:120]
    resumo, tamanho = hashlib.sha256(), 0
    with tempfile.TemporaryDirectory(prefix="arquivo_") as pasta:
        caminho = Path(pasta) / "conteudo"
        with caminho.open("wb") as destino:
            async for parte in request.stream():
                tamanho += len(parte)
                if tamanho > LIMITE_ARQUIVO:  # Content-Length mentiroso não passa
                    return _erro(413, f"arquivo acima de {LIMITE_ARQUIVO} bytes")
                resumo.update(parte)
                destino.write(parte)
        if tamanho == 0:
            return _erro(422, "arquivo vazio")
        tarefa = db.get(TaskExecutionRecord, grant.task_execution_id)
        storage = build_storage_adapters(db)
        artefato = GuardarArquivoEntregue(storage.object_storage, storage.stored_objects, storage.artifacts).execute(
            execution_id=tarefa.execution_id, task_execution_id=grant.task_execution_id,
            execution_attempt_id=grant.execution_attempt_id, caminho=caminho, nome=nome,
            content_type=tipo or "application/octet-stream", sha256=resumo.hexdigest(), tamanho=tamanho,
            metadados={"item": item} if item else {})
        db.commit()
    return JSONResponse(status_code=201, content={"arquivo_id": artefato.id, "nome": artefato.name, "bytes": tamanho})


@router.get("/{job_id}/eventos/estado")
def estado(job_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    grant = _autenticar(db, request, job_id)
    if isinstance(grant, JSONResponse):
        return grant
    sequencias = build_telemetry_adapters(db).events.get_ack_sequences(grant.execution_attempt_id)
    return {"ultima_sequencia": max(sequencias, default=0)}


@router.post("/{job_id}/eventos")
async def receber_eventos(job_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    grant = _autenticar(db, request, job_id)
    if isinstance(grant, JSONResponse):
        return grant
    corpo = await _corpo_json(request)
    if isinstance(corpo, JSONResponse):
        return corpo
    eventos = corpo.get("eventos")
    if not isinstance(eventos, list) or not 1 <= len(eventos) <= LIMITE_EVENTOS:
        return _erro(400, f"eventos precisa ser uma lista de 1 a {LIMITE_EVENTOS}")

    adapters = build_telemetry_adapters(db)
    ja = set(adapters.events.get_ack_sequences(grant.execution_attempt_id))
    aceitos: list[dict[str, Any]] = []
    recusados: list[dict[str, Any]] = []
    consumida = 0
    for evento in eventos:
        sequencia = evento.get("sequence") if isinstance(evento, dict) else None
        if not isinstance(sequencia, int) or isinstance(sequencia, bool) or sequencia < 1:
            recusados.append({"sequence": sequencia, "motivo": "sequence inválida"})
            continue
        consumida = max(consumida, sequencia)
        if sequencia in ja:
            continue  # repetido: idempotente
        try:
            validate_automation_event(evento)
        except TelemetryValidationError as exc:
            recusados.append({"sequence": sequencia, "motivo": str(exc)[:300]})
            continue
        aceitos.append({"event_id": evento["event_id"], "event_sequence": sequencia, "event_type": "automation.event",
                        "occurred_at": evento["occurred_at"], "payload": evento})
    if aceitos:
        try:
            IngestExecutionEventBatch(
                adapters.attempts, adapters.events, adapters.acknowledgements, adapters.metrics, adapters.validator,
                adapters.masker, adapters.realtime, adapters.transaction, projector=adapters.projector,
            ).execute(EventBatchCommand(
                execution_attempt_id=grant.execution_attempt_id, events=aceitos, agent_id=None, agent_instance_id=None,
                executor_type="direct", executor_id=grant.direct_instance_id,
            ))
        except ExecutionAttemptTelemetryError as exc:
            _auditar(db, request, acao="direto.evento_recusado", job_id=job_id,
                     metadados={"instancia": grant.direct_instance_id, "motivo": str(exc)})
            return _erro(409, str(exc))
        except TelemetryValidationError as exc:
            return _erro(400, str(exc))
    ultima = max(max(ja, default=0), consumida)
    return {"ultima_sequencia": ultima, "recusados": recusados}


@router.get("/{job_id}/comandos")
def comandos(job_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    grant = _autenticar(db, request, job_id)
    if isinstance(grant, JSONResponse):
        return grant
    pendentes = SqlAlchemyDirectCommandStore(db).take_pending(grant.execution_attempt_id, datetime.now(UTC))
    db.commit()
    return {"comandos": pendentes}
