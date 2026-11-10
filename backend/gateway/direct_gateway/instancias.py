"""Rotas da instância direta (o lado da automação): inscrição, sessão e próximo job.

Só conexão de saída da máquina; credencial só no corpo ou no cabeçalho, nunca na URL.
Toda recusa responde 401 sem dizer o motivo; o motivo vai para a auditoria.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from infrastructure.database import get_session_factory
from modules.dispatch.application.use_cases.entrega_direta import EntregarProximoJob
from modules.dispatch.application.use_cases.job_tokens import IssueJobToken
from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import (
    SqlAlchemyDirectDeliveryReader,
    SqlAlchemyJobTokenStore,
)
from modules.fleet.application.use_cases.instancias_diretas import (
    AbrirSessao,
    AutenticarSessao,
    Inscrever,
    PedirDesafio,
    Recusado,
)
from modules.fleet.domain.instancia_direta import pode_receber_jobs
from modules.fleet.infrastructure.assinatura import ChaveInvalida, assinatura_confere, validar_chave_publica
from modules.fleet.infrastructure.repositories.sqlalchemy_direct_instances import SqlAlchemyDirectInstanceStore
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.telemetry.infrastructure.realtime.postgres import CANAL_FILA, esperar_aviso, ouvinte

router = APIRouter(prefix="/direto", tags=["modo-direto"])

LIMITE_CORPO = 8_192
ESPERA_MAXIMA_S = 30


def _agora() -> datetime:
    return datetime.now(UTC)


def _erro(codigo: int, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"erro": mensagem})


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _corpo(request: Request) -> dict[str, Any] | JSONResponse:
    if not (request.headers.get("content-type") or "").startswith("application/json"):
        return _erro(415, "envie Content-Type: application/json")
    bruto = b""
    async for parte in request.stream():
        bruto += parte
        if len(bruto) > LIMITE_CORPO:
            return _erro(413, "corpo grande demais")
    try:
        dados = json.loads(bruto or b"{}")
    except ValueError:
        return _erro(400, "JSON inválido")
    return dados if isinstance(dados, dict) else _erro(400, "esperado um objeto JSON")


class _Uso:
    """Sessão de banco curta, com os adaptadores do Fleet e a auditoria."""

    def __init__(self, fabrica: Any) -> None:
        self.fabrica = fabrica

    def __enter__(self) -> "_Uso":
        self.db = self.fabrica()
        self.store = SqlAlchemyDirectInstanceStore(self.db)
        self.audit = build_governance_adapters(self.db).audit
        return self

    def __exit__(self, *exc: Any) -> None:
        if exc[0] is not None:
            self.db.rollback()
        self.db.close()


@router.post("/inscricao", status_code=201)
async def inscrever(request: Request, fabrica: Any = Depends(get_session_factory)) -> Any:
    corpo = await _corpo(request)
    if isinstance(corpo, JSONResponse):
        return corpo
    with _Uso(fabrica) as uso:
        try:
            instancia_id = Inscrever(uso.store, uso.audit, uso.db, validar_chave_publica).execute(
                codigo=str(corpo.get("codigo") or ""), chave_publica=str(corpo.get("chave_publica") or ""),
                nome=corpo.get("nome_maquina"), versao=corpo.get("versao_sdk"), agora=_agora(), ip=_ip(request))
        except ChaveInvalida as exc:
            return _erro(422, str(exc))
        except Recusado as exc:
            uso.db.rollback()
            _auditar_recusa(uso, "direto.inscricao.recusada", exc.motivo, request)
            return _erro(401, "código de inscrição inválido, vencido ou já usado")
    return JSONResponse(status_code=201, content={"instancia_id": instancia_id, "status": "pendente"})


@router.post("/sessao/desafio")
async def desafio(request: Request, fabrica: Any = Depends(get_session_factory)) -> Any:
    corpo = await _corpo(request)
    if isinstance(corpo, JSONResponse):
        return corpo
    with _Uso(fabrica) as uso:
        try:
            return PedirDesafio(uso.store, uso.db).execute(instancia_id=str(corpo.get("instancia_id") or ""), agora=_agora())
        except Recusado as exc:
            _auditar_recusa(uso, "direto.desafio.recusado", exc.motivo, request, recurso=str(corpo.get("instancia_id") or ""))
            return _erro(401, "instância não pode abrir sessão")


@router.post("/sessao")
async def sessao(request: Request, fabrica: Any = Depends(get_session_factory)) -> Any:
    corpo = await _corpo(request)
    if isinstance(corpo, JSONResponse):
        return corpo
    with _Uso(fabrica) as uso:
        try:
            aberta = AbrirSessao(uso.store, uso.audit, uso.db, assinatura_confere).execute(
                instancia_id=str(corpo.get("instancia_id") or ""), desafio_id=str(corpo.get("desafio_id") or ""),
                assinatura=str(corpo.get("assinatura") or ""), agora=_agora(), ip=_ip(request))
        except Recusado:
            return _erro(401, "sessão recusada")
    return {"token": aberta.token, "expira_em": aberta.expira_em.isoformat(), "status": aberta.status}


def _autenticar(uso: _Uso, request: Request) -> Any:
    autorizacao = request.headers.get("authorization") or ""
    token = autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else None
    try:
        instancia = AutenticarSessao(uso.store).execute(token=token, agora=_agora())
        uso.db.commit()  # último sinal
        return instancia
    except Recusado as exc:
        uso.db.rollback()
        _auditar_recusa(uso, "direto.sessao.recusada", exc.motivo, request)
        return None


@router.get("/status")
def status(request: Request, fabrica: Any = Depends(get_session_factory)) -> Any:
    """Situação da instância: a automação mostra "aguardando aprovação" enquanto pendente."""
    with _Uso(fabrica) as uso:
        instancia = _autenticar(uso, request)
        if instancia is None:
            return _erro(401, "sessão inválida")
        return {"instancia_id": instancia.id, "status": instancia.status, "maquina_id": instancia.machine_id,
                "recebe_jobs": pode_receber_jobs(instancia.status)}


@router.get("/jobs/proximo")
async def proximo_job(request: Request, espera: int = 0, fabrica: Any = Depends(get_session_factory)) -> Any:
    """O próximo job reservado para esta instância. Com ``espera``, aguarda até N s (máx. 30)."""
    espera = max(0, min(espera, ESPERA_MAXIMA_S))
    with _Uso(fabrica) as uso:
        instancia = _autenticar(uso, request)
        if instancia is None:
            return _erro(401, "sessão inválida")
    if not pode_receber_jobs(instancia.status):
        return {"job": None, "status": instancia.status}
    limite = asyncio.get_running_loop().time() + espera
    async with ouvinte.assinar(CANAL_FILA, "") as sinal:
        while True:
            job = await asyncio.to_thread(_entregar, fabrica, instancia.id)
            if job is not None or asyncio.get_running_loop().time() >= limite or await request.is_disconnected():
                return {"job": job, "status": instancia.status}
            await esperar_aviso(sinal, min(5.0, max(limite - asyncio.get_running_loop().time(), 0.1)))


def _entregar(fabrica: Any, instancia_id: str) -> dict[str, Any] | None:
    with fabrica() as db:
        return EntregarProximoJob(SqlAlchemyDirectDeliveryReader(db), IssueJobToken(SqlAlchemyJobTokenStore(db)).execute,
                                  db).execute(instancia_id=instancia_id, agora=_agora())


def _auditar_recusa(uso: _Uso, acao: str, motivo: str, request: Request, recurso: str = "") -> None:
    from uuid import uuid4

    from modules.governance.domain.audit import AuditEvent

    try:
        uso.audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="direct_instance", actor_id=recurso or None, action=acao,
            resource_type="direct_instance", resource_id=recurso or "desconhecida",
            metadata={"motivo": motivo}, ip=_ip(request), user_agent=request.headers.get("user-agent"),
            occurred_at=_agora()))
        uso.db.commit()
    except Exception:  # noqa: BLE001 - auditoria não derruba a resposta de recusa
        uso.db.rollback()
