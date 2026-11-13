"""Envio por e-mail (Microsoft Graph): desligado por padrão, um pedido certo, segredo nunca exposto.

Sem rede: um transporte HTTP de teste responde no lugar da Microsoft.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from modules.telemetry.application.use_cases.notificacoes import (
    TENTATIVAS_DE_ENVIO,
    VALIDADE_DO_ENVIO,
    EnviarAvisos,
    ErroDeEnvio,
    corpo_do_email,
)
from modules.telemetry.infrastructure.email_graph import GraphCarteiro, montar_carteiro, situacao_do_envio

SEGREDO = "segredo-de-teste-que-nao-pode-vazar"
AGORA = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


def _config(**kw):
    base = {"notificacoes_email_ligado": False, "graph_tenant_id": "t-1", "graph_client_id": "app-1",
            "graph_client_secret": SecretStr(SEGREDO), "graph_remetente": "portal@biason.invalid"}
    return SimpleNamespace(**{**base, **kw})


def test_liga_sozinho_com_os_quatro_dados_e_incompleto_sem_todos() -> None:
    """13/11/2026: sem NOTIFICACOES_EMAIL_LIGADO, liga sozinho com tenant, aplicativo, segredo e remetente;
    "false" força desligado; "true" sem todos os dados fica incompleto."""
    from infrastructure.config import Settings

    assert Settings.model_fields["notificacoes_email_ligado"].default is None
    assert situacao_do_envio(_config(notificacoes_email_ligado=None)) == "ligado"
    assert situacao_do_envio(_config(notificacoes_email_ligado=None, graph_remetente="")) == "desligado"
    assert situacao_do_envio(_config()) == "desligado" and montar_carteiro(_config()) is None
    assert situacao_do_envio(_config(notificacoes_email_ligado=True)) == "ligado"
    for campo, vazio in [("graph_tenant_id", ""), ("graph_client_id", ""), ("graph_client_secret", SecretStr("")),
                         ("graph_remetente", "")]:
        assert situacao_do_envio(_config(notificacoes_email_ligado=True, **{campo: vazio})) == "incompleto"
        assert montar_carteiro(_config(notificacoes_email_ligado=True, **{campo: vazio})) is None
    assert isinstance(montar_carteiro(_config(notificacoes_email_ligado=True)), GraphCarteiro)


def _carteiro(respostas: dict[str, httpx.Response], pedidos: list[httpx.Request]) -> GraphCarteiro:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return respostas["login" if "login.microsoftonline.com" in pedido.url.host else "enviar"]

    return GraphCarteiro("t-1", "app-1", SEGREDO, "portal@biason.invalid", httpx.Client(transport=httpx.MockTransport(responder)))


def test_envia_com_token_de_aplicativo_e_reaproveita_o_token() -> None:
    pedidos: list[httpx.Request] = []
    c = _carteiro({"login": httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
                   "enviar": httpx.Response(202)}, pedidos)
    c.enviar("folha@biason.invalid", "Folha: concluída", "texto")
    c.enviar("outra@biason.invalid", "Folha: concluída", "texto")
    assert [str(p.url) for p in pedidos] == [
        "https://login.microsoftonline.com/t-1/oauth2/v2.0/token",
        "https://graph.microsoft.com/v1.0/users/portal@biason.invalid/sendMail",
        "https://graph.microsoft.com/v1.0/users/portal@biason.invalid/sendMail",
    ]
    login = dict(x.split("=", 1) for x in pedidos[0].content.decode().split("&"))
    assert login["grant_type"] == "client_credentials" and login["client_id"] == "app-1"
    assert pedidos[1].headers["authorization"] == "Bearer tok-1"
    corpo = json.loads(pedidos[1].content)
    assert corpo == {"message": {"subject": "Folha: concluída", "body": {"contentType": "Text", "content": "texto"},
                                 "toRecipients": [{"emailAddress": {"address": "folha@biason.invalid"}}]},
                     "saveToSentItems": False}
    assert all(SEGREDO not in str(p.url) for p in pedidos)  # segredo só no corpo do login, nunca na URL
    assert SEGREDO not in repr(c)


@pytest.mark.parametrize("respostas,trecho", [
    ({"login": httpx.Response(401, json={"error": "invalid_client"}), "enviar": httpx.Response(202)},
     "login no Microsoft Graph recusado (HTTP 401)"),
    ({"login": httpx.Response(200, json={"access_token": "tok"}), "enviar": httpx.Response(403, json={"error": {"code": "ErrorAccessDenied"}})},
     "Microsoft Graph recusou o envio (HTTP 403, ErrorAccessDenied)"),
    ({"login": httpx.Response(200, json={"access_token": "tok"}), "enviar": httpx.Response(500, text="oops")},
     "Microsoft Graph recusou o envio (HTTP 500)"),
])
def test_recusa_vira_erro_sem_o_segredo(respostas, trecho) -> None:
    with pytest.raises(ErroDeEnvio) as exc:
        _carteiro(respostas, []).enviar("a@b.invalid", "x", "y")
    assert str(exc.value) == trecho and SEGREDO not in str(exc.value)


def test_falha_de_rede_vira_erro_sem_detalhes() -> None:
    def cair(_pedido):
        raise httpx.ConnectError(f"falhou com {SEGREDO}")

    c = GraphCarteiro("t", "a", SEGREDO, "r@x.invalid", httpx.Client(transport=httpx.MockTransport(cair)))
    with pytest.raises(ErroDeEnvio) as exc:
        c.enviar("a@b.invalid", "x", "y")
    assert str(exc.value) == "login no Microsoft Graph falhou: ConnectError" and exc.value.__cause__ is None


def test_corpo_do_email() -> None:
    assert corpo_do_email("T", "X", "/execucoes/exe_1", "https://portal.biason.invalid/") == (
        "T\n\nX\n\nAbrir no portal: https://portal.biason.invalid/execucoes/exe_1\n\n--\n"
        "Portal de Automações Biason. Para mudar o que recebe: Configurações > Notificações.")
    assert "Abrir no portal" not in corpo_do_email("T", "X", None, "https://p")


# --- EnviarAvisos ------------------------------------------------------------------------------

class _Avisos:
    def __init__(self, linhas) -> None:
        self.linhas = linhas

    def pendentes(self, limite):
        return self.linhas[:limite]


class _Carteiro:
    def __init__(self, falhar_para: set[str] = frozenset()) -> None:
        self.enviados: list[tuple[str, str]] = []
        self.falhar_para = falhar_para

    def enviar(self, para, assunto, texto):
        if para in self.falhar_para:
            raise ErroDeEnvio("recusado")
        self.enviados.append((para, assunto))


class _Tx:
    vezes = 0

    def commit(self):
        self.vezes += 1


def _aviso(email: str, idade: timedelta, tentativas: int = 0):
    return (SimpleNamespace(email=email, created_at=AGORA - idade, email_status="pendente", tentativas=tentativas,
                            ultimo_erro=None, enviado_em=None),
            SimpleNamespace(titulo="Folha: concluída", texto="t", link="/execucoes/e"))


def test_sem_carteiro_nada_sai_e_nada_muda() -> None:
    linhas = [_aviso("a@x.invalid", timedelta(minutes=1))]
    tx = _Tx()
    assert EnviarAvisos(_Avisos(linhas), None, tx, "https://p").execute() == {"ligado": 0}
    assert linhas[0][0].email_status == "pendente" and tx.vezes == 0


def test_envia_expira_o_velho_e_conta_falhas() -> None:
    novo, velho = _aviso("a@x.invalid", timedelta(minutes=1)), _aviso("b@x.invalid", VALIDADE_DO_ENVIO + timedelta(seconds=1))
    limite = _aviso("d@x.invalid", VALIDADE_DO_ENVIO)
    falha, ultima = _aviso("c@x.invalid", timedelta(minutes=1)), _aviso("e@x.invalid", timedelta(minutes=1), TENTATIVAS_DE_ENVIO - 1)
    carteiro, tx = _Carteiro({"c@x.invalid", "e@x.invalid"}), _Tx()
    r = EnviarAvisos(_Avisos([novo, velho, limite, falha, ultima]), carteiro, tx, "https://p", agora=lambda: AGORA).execute()
    assert r == {"ligado": 1, "enviados": 2, "expirados": 1, "falhas": 2} and tx.vezes == 1
    assert carteiro.enviados == [("a@x.invalid", "Folha: concluída"), ("d@x.invalid", "Folha: concluída")]
    assert (novo[0].email_status, novo[0].enviado_em) == ("enviado", AGORA)
    assert velho[0].email_status == "expirado"
    assert (falha[0].email_status, falha[0].tentativas, falha[0].ultimo_erro) == ("pendente", 1, "recusado")
    assert (ultima[0].email_status, ultima[0].tentativas) == ("falhou", TENTATIVAS_DE_ENVIO)
    assert (VALIDADE_DO_ENVIO, TENTATIVAS_DE_ENVIO) == (timedelta(hours=6), 5)


def test_respeita_o_limite_do_lote() -> None:
    linhas = [_aviso(f"{i}@x.invalid", timedelta(minutes=1)) for i in range(3)]
    carteiro = _Carteiro()
    EnviarAvisos(_Avisos(linhas), carteiro, _Tx(), "https://p", agora=lambda: AGORA).execute(limite=2)
    assert len(carteiro.enviados) == 2
