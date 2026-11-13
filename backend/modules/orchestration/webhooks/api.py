"""API dos webhooks (13/11/2026). Regras em ``aplicacao.py``.

Gestão (com login):
- ``GET /webhooks?automacao=``: ``webhooks.ver`` ou ``automacoes.ver``; só das automações que a pessoa vê.
- ``POST /webhooks``, ``PUT /webhooks/{id}``, ``POST /webhooks/{id}/token``, ``DELETE /webhooks/{id}``:
  ``webhooks.gerenciar`` e poder **executar** a automação. O token volta uma única vez, sem cache.
- ``GET /webhooks/{id}/chamadas``: as últimas chamadas recebidas.

Pública (sem login, só o token do webhook): ``POST /webhooks/{id}``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import acesso_por_automacao, precisa
from modules.access.api.dependencies import get_current_user
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.orchestration.webhooks.aplicacao import (
    LIMITE_CORPO,
    PARAMETROS_COM_TOKEN,
    Chamada,
    Recusa,
    SemPermissao,
    WebhookInvalido,
    WebhookNaoEncontrado,
    Webhooks,
)
from modules.orchestration.webhooks.repositorio import SqlAlchemyWebhooks

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

VER = [Depends(precisa("webhooks.ver", "webhooks.gerenciar", "automacoes.ver"))]
GERENCIAR = [Depends(precisa("webhooks.gerenciar"))]
SEM_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class _Transacao:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


def webhooks(db: Session) -> Webhooks:
    from modules.catalog.api.itens import pedir_execucao_da_automacao

    def pedir(automation_id: int, corpo: dict[str, Any], solicitante: str) -> dict[str, Any]:
        try:
            return pedir_execucao_da_automacao(db, automation_id, corpo, solicitante=solicitante, origem="webhook")
        except HTTPException as exc:  # o mesmo motivo do Executar, para quem chamou
            if isinstance(exc.detail, dict):
                raise Recusa(422, "campos de entrada inválidos", exc.detail.get("campos", exc.detail)) from exc
            raise Recusa(422 if exc.status_code < 500 else 503, str(exc.detail)) from exc

    acesso = acesso_por_automacao(db)
    return Webhooks(SqlAlchemyWebhooks(db), lambda user, aid, acao: acesso.pode(user, aid, acao),
                    build_governance_adapters(db).audit, _Transacao(db), pedir)


def _url(webhook_id: str) -> str:
    return f"{get_settings().backend_public_url.rstrip('/')}{get_settings().api_v1_prefix}/webhooks/{webhook_id}"


def _com_url(dados: dict[str, Any]) -> dict[str, Any]:
    return {**dados, "url": _url(dados["id"])}


def _fazer(db: Session, acao: Any) -> Any:
    try:
        return acao()
    except WebhookNaoEncontrado as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SemPermissao as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WebhookInvalido as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", dependencies=VER)
def listar(automacao: int | None = Query(default=None), db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"webhooks": [_com_url(w) for w in webhooks(db).listar(user, automacao)]}


@router.post("", status_code=201, dependencies=GERENCIAR)
def criar(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    criado = _fazer(db, lambda: webhooks(db).criar(user, corpo))
    criado["webhook"] = _com_url(criado["webhook"])
    return JSONResponse(status_code=201, content=jsonable_encoder(criado), headers=SEM_CACHE)


@router.get("/{webhook_id}/chamadas", dependencies=VER)
def chamadas(webhook_id: str, limite: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db),
             user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"chamadas": _fazer(db, lambda: webhooks(db).chamadas(user, webhook_id, limite))}


@router.get("/{webhook_id}", dependencies=VER)
def ver(webhook_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"webhook": _com_url(_fazer(db, lambda: webhooks(db).ver(user, webhook_id)))}


@router.put("/{webhook_id}", dependencies=GERENCIAR)
def mudar(webhook_id: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
          user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"webhook": _com_url(_fazer(db, lambda: webhooks(db).mudar(user, webhook_id, corpo)))}


@router.post("/{webhook_id}/token", dependencies=GERENCIAR)
def gerar_token(webhook_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    gerado = _fazer(db, lambda: webhooks(db).gerar_token(user, webhook_id))
    gerado["webhook"] = _com_url(gerado["webhook"])
    return JSONResponse(content=jsonable_encoder(gerado), headers=SEM_CACHE)


@router.delete("/{webhook_id}", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def apagar(webhook_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    _fazer(db, lambda: webhooks(db).apagar(user, webhook_id))


@router.post("/{webhook_id}", include_in_schema=True, summary="Acionar a automação do webhook (sem login, token no cabeçalho)")
async def acionar(webhook_id: str, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    autorizacao = request.headers.get("authorization") or ""
    token = autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else None
    corpo = b""
    async for parte in request.stream():
        corpo += parte
        if len(corpo) > LIMITE_CORPO:  # Content-Length mentiroso não passa
            break
    chamada = Chamada(webhook_id=webhook_id[:40], token=token, ip=request.client.host if request.client else None,
                      user_agent=request.headers.get("user-agent"), chave_idempotencia=request.headers.get("idempotency-key"),
                      tipo_do_conteudo=request.headers.get("content-type"), corpo=corpo,
                      token_na_url=any(k.lower() in PARAMETROS_COM_TOKEN for k in request.query_params.keys()))
    codigo, resposta = webhooks(db).acionar(chamada)
    return JSONResponse(status_code=codigo, content=jsonable_encoder(resposta), headers=SEM_CACHE)
