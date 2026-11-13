"""API do login com código, esqueci a senha, convite e trocar a senha (13/11/2026). Regras em
``application/acesso.py``.

Sem login:
- ``POST /auth/login`` ``{email, password, dispositivo?}`` → ``{access_token}`` ou
  ``{precisa_codigo, desafio, email, codigo_vale_ate, tentativas}``.
- ``POST /auth/codigo`` ``{desafio, codigo, confiar}`` → ``{access_token, dispositivo?}``.
- ``POST /auth/codigo/reenviar`` ``{desafio}``.
- ``POST /auth/esqueci`` ``{email}``: sempre ``200`` com a mesma resposta.
- ``POST /auth/senha/ver`` ``{token}`` e ``POST /auth/senha`` ``{token, senha}``: o link do e-mail.
Com login: ``POST /auth/trocar-senha`` ``{atual, nova}``; ``GET``/``DELETE /auth/navegadores``.
Quem gerencia usuários: ``POST /users/{id}/convite`` (manda o link de criar a senha de novo).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import precisa
from modules.access.api.dependencies import get_current_user
from modules.access.application.acesso import Acesso, CodigoInvalido, LinkInvalido, SenhaFraca
from modules.access.domain import AuthenticationFailed

router = APIRouter(tags=["access"])
SEM_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def acesso(db: Session) -> Acesso:
    from modules.access.infrastructure.adapters import build_access_adapters
    from modules.access.infrastructure.repositories.sqlalchemy_acesso import SqlAlchemyAcesso
    from modules.governance.infrastructure.adapters import build_governance_adapters
    from modules.telemetry.correio.api import build_correio
    from modules.telemetry.correio.correio import Contexto, validar
    from modules.telemetry.infrastructure.email_graph import situacao_do_envio

    settings = get_settings()
    adapters = build_access_adapters(db)

    def enviar(para: str, assunto: str, corpo: str, tipo: str) -> bool:
        registro = build_correio(db).pedir(Contexto(origem="portal", tipo=tipo), validar({"para": [para], "assunto": assunto, "html": corpo}),
                                           sigiloso=True)
        return registro.situacao == "enviado"

    return Acesso(SqlAlchemyAcesso(db), adapters.passwords, adapters.tokens, build_governance_adapters(db).audit, settings.secret_key,
                  settings.frontend_url, enviar if situacao_do_envio(settings) == "ligado" else None)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _responder(db: Session, acao: Any, status: int = 200) -> JSONResponse:
    try:
        resultado = acao()
        db.commit()
    except AuthenticationFailed as exc:
        db.commit()  # a tentativa (e a trava) ficam gravadas
        return JSONResponse(status_code=401, content={"erro": str(exc)}, headers=SEM_CACHE)
    except CodigoInvalido as exc:
        db.commit()
        return JSONResponse(status_code=401, content={"erro": str(exc), "restantes": exc.restantes,
                                                      "voltar_ao_login": exc.voltar_ao_login}, headers=SEM_CACHE)
    except LinkInvalido as exc:
        db.rollback()
        return JSONResponse(status_code=410, content={"erro": str(exc)}, headers=SEM_CACHE)
    except SenhaFraca as exc:
        db.rollback()
        return JSONResponse(status_code=422, content={"erro": str(exc)}, headers=SEM_CACHE)
    return JSONResponse(status_code=status, content=jsonable_encoder(resultado), headers=SEM_CACHE)


@router.post("/auth/login")
def entrar(request: Request, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    return _responder(db, lambda: acesso(db).entrar(str(corpo.get("email") or ""), str(corpo.get("password") or ""),
                                                    corpo.get("dispositivo") or None, _ip(request), request.headers.get("user-agent")))


@router.post("/auth/codigo")
def confirmar_codigo(request: Request, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    return _responder(db, lambda: acesso(db).confirmar_codigo(str(corpo.get("desafio") or ""), str(corpo.get("codigo") or ""),
                                                              bool(corpo.get("confiar")), _ip(request), request.headers.get("user-agent")))


@router.post("/auth/codigo/reenviar")
def reenviar_codigo(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    return _responder(db, lambda: acesso(db).reenviar_codigo(str(corpo.get("desafio") or "")))


@router.post("/auth/esqueci")
def esqueci(request: Request, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    def pedir() -> dict[str, str]:
        acesso(db).esqueci(str(corpo.get("email") or ""), _ip(request))
        return {"mensagem": "Se o e-mail tiver conta no Portal, mandamos um link para criar uma senha nova. Veja a caixa de entrada."}

    return _responder(db, pedir)


@router.post("/auth/senha/ver")
def ver_link(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    return _responder(db, lambda: acesso(db).ver_link(str(corpo.get("token") or "")))


@router.post("/auth/senha")
def definir_senha(request: Request, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    def definir() -> dict[str, str]:
        acesso(db).definir_senha(str(corpo.get("token") or ""), str(corpo.get("senha") or ""), _ip(request))
        return {"mensagem": "Senha salva. Entre com ela."}

    return _responder(db, definir)


@router.post("/auth/trocar-senha")
def trocar_senha(request: Request, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                 user: Any = Depends(get_current_user)) -> JSONResponse:
    def trocar() -> dict[str, str]:
        acesso(db).trocar_senha(int(user.id), str(corpo.get("atual") or ""), str(corpo.get("nova") or ""), _ip(request))
        return {"mensagem": "Senha trocada. Os navegadores confiáveis vão pedir o código de novo."}

    return _responder(db, trocar)


@router.get("/auth/navegadores")
def navegadores(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"navegadores": acesso(db).navegadores(int(user.id))}


@router.delete("/auth/navegadores")
def esquecer_navegadores(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> JSONResponse:
    return _responder(db, lambda: {"esquecidos": acesso(db).esquecer_navegadores(int(user.id))})


@router.post("/users/{user_id}/convite", dependencies=[Depends(precisa("usuarios.gerenciar"))])
def mandar_convite(user_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    def mandar() -> dict[str, Any]:
        enviado = acesso(db).convidar(user_id, _ip(request))
        if not enviado:
            raise HTTPException(status_code=422, detail="Não deu para mandar: o envio de e-mail está desligado ou o e-mail da pessoa não recebe mensagens.")
        return {"enviado": True}

    return _responder(db, mandar)
