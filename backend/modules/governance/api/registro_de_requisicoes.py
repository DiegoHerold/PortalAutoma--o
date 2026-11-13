"""Registro de requisições (12/11/2026): toda alteração feita por uma pessoa no Portal vai para a
auditoria, mesmo quando a tela não registra nada por conta própria.

- Cada requisição ganha um identificador (``x-request-id``); tudo o que ela gravar na auditoria
  leva esse identificador, e a tela junta "o que esta ação fez".
- Alteração = POST, PUT, PATCH ou DELETE com login de pessoa. Fica com a ação ``api.<método>``,
  a rota, o resultado (status) e o tempo. Leitura (GET) não entra: as telas releem a cada poucos
  segundos e isso afogaria o que importa.
- Fora: o login (já registrado), o tráfego das máquinas (``/direto``, Agents) e o registro de
  telas abertas (que já é um evento de auditoria).
- Nunca derruba a requisição: se a gravação falhar, fica no log do servidor.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from infrastructure.database import get_session_factory
from infrastructure.requisicao import Requisicao, atual

log = logging.getLogger(__name__)

ALTERACOES = {"POST", "PUT", "PATCH", "DELETE"}
FORA = ("/auth/login", "/direto/", "/agents/", "/agent/", "/gateway/", "/ws/", "/governance/auditoria/tela")


def _quem(request: Request) -> str | None:
    cabecalho = request.headers.get("authorization") or ""
    if not cabecalho.lower().startswith("bearer "):
        return None
    token = cabecalho[7:].strip()
    if token.startswith("psa_"):  # conta de serviço: o usuário técnico é resolvido ao gravar
        from modules.access.application.contas_de_servico import hash_da_credencial

        return "psa:" + hash_da_credencial(token)
    try:
        from modules.access.infrastructure.authentication.tokens import JwtTokenIssuer

        dados = JwtTokenIssuer().decode_access_token(cabecalho[7:].strip())
    except Exception:  # noqa: BLE001 - token inválido: a própria rota responde 401
        return None
    if dados.get("scope"):  # tokens de download de pacote etc. não são de pessoa
        return None
    sujeito = dados.get("sub")
    return str(sujeito) if sujeito else None


def recurso_da_rota(caminho: str, prefixo: str) -> tuple[str, str]:
    """``/api/v1/schedules/12/pause`` → (``schedules``, ``12``)."""
    partes = [p for p in caminho.removeprefix(prefixo).split("/") if p]
    if not partes:
        return "portal", "-"
    return partes[0][:120], (partes[1][:120] if len(partes) > 1 else "-")


def deve_registrar(metodo: str, caminho: str, prefixo: str) -> bool:
    if metodo not in ALTERACOES or not caminho.startswith(prefixo):
        return False
    resto = caminho.removeprefix(prefixo)
    return not any(resto.startswith(f) for f in FORA)


def _gravar(app: FastAPI, dados: dict[str, Any]) -> None:
    from modules.governance.domain.audit import AuditEvent
    from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository

    fabrica = app.dependency_overrides.get(get_session_factory, get_session_factory)()
    try:
        with fabrica() as db:
            if str(dados.get("actor_id") or "").startswith("psa:"):
                from sqlalchemy import text

                linha = db.execute(text("SELECT id, user_id FROM service_accounts WHERE credential_hash = :h"),
                                   {"h": dados["actor_id"][4:]}).first()
                if linha is None or linha[1] is None:
                    return  # credencial inválida: a recusa já foi auditada na autenticação
                dados = {**dados, "actor_id": str(linha[1]), "metadata": {**dados["metadata"], "conta_de_servico": linha[0]}}
            SqlAlchemyAuditEventRepository(db).append(AuditEvent(**dados))
            db.commit()
    except Exception:  # noqa: BLE001 - a auditoria da requisição nunca derruba a resposta
        log.exception("não foi possível registrar a requisição %s na auditoria", dados.get("metadata", {}).get("caminho"))


def instalar(app: FastAPI, prefixo: str) -> None:
    @app.middleware("http")
    async def registrar_requisicoes(request: Request, call_next):
        correlacao = (request.headers.get("x-request-id") or "")[:80] or f"req_{uuid4().hex}"
        ip = request.client.host if request.client else None
        marca = atual.set(Requisicao(correlacao, ip, (request.headers.get("user-agent") or "")[:400] or None))
        inicio = time.monotonic()
        try:
            resposta = await call_next(request)
        finally:
            atual.reset(marca)
        resposta.headers["x-request-id"] = correlacao
        caminho = request.url.path
        if deve_registrar(request.method, caminho, prefixo):
            quem = _quem(request)
            if quem:
                rota = getattr(request.scope.get("route"), "path", None)
                tipo, identificador = recurso_da_rota(caminho, prefixo)
                await run_in_threadpool(_gravar, request.app, {
                    "id": f"aud_{uuid4().hex}", "actor_type": "user", "actor_id": quem,
                    "action": f"api.{request.method.lower()}", "resource_type": tipo, "resource_id": identificador,
                    "metadata": {"metodo": request.method, "caminho": caminho, "rota": rota, "status": resposta.status_code,
                                 "duracao_ms": round((time.monotonic() - inicio) * 1000)},
                    "correlation_id": correlacao, "ip": ip, "user_agent": request.headers.get("user-agent"),
                    "occurred_at": datetime.now(UTC)})
        return resposta
