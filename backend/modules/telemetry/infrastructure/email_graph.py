"""Envio de e-mail pelo Microsoft Graph (Fase 6), com credencial de aplicativo.

Só existe se ``NOTIFICACOES_EMAIL_LIGADO=true`` e o tenant, o aplicativo, o segredo e o
remetente estiverem no ``.env``. HTTPS com certificado sempre validado (sem opção de
desligar). O segredo e o token nunca vão para log, URL ou mensagem de erro.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

from modules.telemetry.application.use_cases.notificacoes import ErroDeEnvio

LOGIN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
ENVIAR = "https://graph.microsoft.com/v1.0/users/{remetente}/sendMail"


class GraphCarteiro:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, remetente: str,
                 cliente: httpx.Client | None = None) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._segredo = client_secret
        self.remetente = remetente
        self.cliente = cliente or httpx.Client(timeout=15.0)  # verify=True é o padrão e não muda
        self._token: tuple[str, float] | None = None

    def __repr__(self) -> str:  # nunca mostra o segredo
        return f"GraphCarteiro(remetente={self.remetente!r})"

    def _token_valido(self) -> str:
        if self._token and self._token[1] > time.monotonic() + 60:
            return self._token[0]
        try:
            r = self.cliente.post(LOGIN.format(tenant=quote(self.tenant_id, safe="")), data={
                "client_id": self.client_id, "client_secret": self._segredo,
                "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
        except httpx.HTTPError as exc:
            raise ErroDeEnvio(f"login no Microsoft Graph falhou: {type(exc).__name__}") from None
        if r.status_code != 200:
            raise ErroDeEnvio(f"login no Microsoft Graph recusado (HTTP {r.status_code})")
        corpo = r.json()
        self._token = (corpo["access_token"], time.monotonic() + float(corpo.get("expires_in", 3599)))
        return self._token[0]

    def enviar(self, para: str, assunto: str, texto: str) -> None:
        mensagem: dict[str, Any] = {
            "message": {"subject": assunto, "body": {"contentType": "Text", "content": texto},
                        "toRecipients": [{"emailAddress": {"address": para}}]},
            "saveToSentItems": False,
        }
        token = self._token_valido()
        try:
            r = self.cliente.post(ENVIAR.format(remetente=quote(self.remetente, safe="@")), json=mensagem,
                                  headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise ErroDeEnvio(f"envio pelo Microsoft Graph falhou: {type(exc).__name__}") from None
        if r.status_code != 202:
            codigo = ""
            try:
                codigo = str((r.json().get("error") or {}).get("code") or "")
            except ValueError:
                pass
            raise ErroDeEnvio(f"Microsoft Graph recusou o envio (HTTP {r.status_code}{', ' + codigo if codigo else ''})")


def situacao_do_envio(settings: Any) -> str:
    """``desligado``, ``incompleto`` (ligado sem todos os dados) ou ``ligado``."""
    if not settings.notificacoes_email_ligado:
        return "desligado"
    completo = all([settings.graph_tenant_id, settings.graph_client_id,
                    settings.graph_client_secret.get_secret_value(), settings.graph_remetente])
    return "ligado" if completo else "incompleto"


def montar_carteiro(settings: Any) -> GraphCarteiro | None:
    if situacao_do_envio(settings) != "ligado":
        return None
    return GraphCarteiro(settings.graph_tenant_id, settings.graph_client_id,
                         settings.graph_client_secret.get_secret_value(), settings.graph_remetente)
