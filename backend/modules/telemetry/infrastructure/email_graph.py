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
            raise ErroDeEnvio(f"login no Microsoft Graph falhou: {type(exc).__name__}", temporario=True) from None
        if r.status_code != 200:
            raise ErroDeEnvio(f"login no Microsoft Graph recusado (HTTP {r.status_code})",
                              temporario=r.status_code == 429 or r.status_code >= 500)
        corpo = r.json()
        self._token = (corpo["access_token"], time.monotonic() + float(corpo.get("expires_in", 3599)))
        return self._token[0]

    def enviar(self, para: str | list[str], assunto: str, texto: str, *, html: str | None = None,
               cc: list[str] | tuple[str, ...] = (), cco: list[str] | tuple[str, ...] = (),
               anexos: list[tuple[str, str, bytes]] | tuple = (), responder_para: str | None = None) -> None:
        """Envia uma mensagem. ``anexos``: (nome, tipo, conteúdo). Erro de rede, 429 ou 5xx levanta
        ``ErroDeEnvio`` com ``temporario=True`` (vale tentar de novo); o resto, ``temporario=False``."""
        import base64

        destinos = [para] if isinstance(para, str) else list(para)
        mensagem: dict[str, Any] = {
            "message": {
                "subject": assunto,
                "body": {"contentType": "HTML", "content": html} if html else {"contentType": "Text", "content": texto},
                "toRecipients": [{"emailAddress": {"address": e}} for e in destinos],
                **({"ccRecipients": [{"emailAddress": {"address": e}} for e in cc]} if cc else {}),
                **({"bccRecipients": [{"emailAddress": {"address": e}} for e in cco]} if cco else {}),
                **({"replyTo": [{"emailAddress": {"address": responder_para}}]} if responder_para else {}),
                **({"attachments": [{"@odata.type": "#microsoft.graph.fileAttachment", "name": nome, "contentType": tipo,
                                     "contentBytes": base64.b64encode(conteudo).decode("ascii")}
                                    for nome, tipo, conteudo in anexos]} if anexos else {}),
            },
            "saveToSentItems": False,
        }
        token = self._token_valido()
        try:
            r = self.cliente.post(ENVIAR.format(remetente=quote(self.remetente, safe="@")), json=mensagem,
                                  headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise ErroDeEnvio(f"envio pelo Microsoft Graph falhou: {type(exc).__name__}", temporario=True) from None
        if r.status_code != 202:
            codigo = ""
            try:
                codigo = str((r.json().get("error") or {}).get("code") or "")
            except ValueError:
                pass
            raise ErroDeEnvio(f"Microsoft Graph recusou o envio (HTTP {r.status_code}{', ' + codigo if codigo else ''})",
                              temporario=r.status_code == 429 or r.status_code >= 500)


def situacao_do_envio(settings: Any) -> str:
    """``desligado``, ``incompleto`` (ligado sem todos os dados) ou ``ligado``.

    ``notificacoes_email_ligado`` ``None`` (sem a variável no .env): liga sozinho com os quatro dados."""
    completo = all([settings.graph_tenant_id, settings.graph_client_id,
                    settings.graph_client_secret.get_secret_value(), settings.graph_remetente])
    ligado = getattr(settings, "notificacoes_email_ligado", None)
    if ligado is None:
        return "ligado" if completo else "desligado"
    if not ligado:
        return "desligado"
    return "ligado" if completo else "incompleto"


def montar_carteiro(settings: Any) -> GraphCarteiro | None:
    if situacao_do_envio(settings) != "ligado":
        return None
    return GraphCarteiro(settings.graph_tenant_id, settings.graph_client_id,
                         settings.graph_client_secret.get_secret_value(), settings.graph_remetente)
