"""E-mail centralizado (13/11/2026) no PostgreSQL e pela API real, com um carteiro falso no lugar do Graph."""

from __future__ import annotations

import base64

from sqlalchemy import text

from modules.telemetry.application.use_cases.notificacoes import ErroDeEnvio
from tests.db.test_comunicacao import _rodando
from tests.db.test_modo_direto_inscricao import admin  # noqa: F401 - fixture


class Carteiro:
    def __init__(self) -> None:
        self.enviados: list[dict] = []
        self.falhar: ErroDeEnvio | None = None

    def enviar(self, para, assunto, texto, **extra) -> None:
        if self.falhar is not None:
            raise self.falhar
        self.enviados.append({"para": para, "assunto": assunto, "texto": texto, **extra})


def test_automacao_pede_email_pelo_portal(cliente, sessao, admin, monkeypatch) -> None:
    import modules.telemetry.infrastructure.email_graph as graph

    carteiro = Carteiro()
    monkeypatch.setattr(graph, "montar_carteiro", lambda settings: carteiro)
    _, _, execution_id, job_id, tentativa, cab_job = _rodando(cliente, sessao, admin, "9101")
    url = f"/api/v1/direto/jobs/{job_id}/emails"
    pedido = {"para": ["analista@cliente-teste.com.br"], "cc": "gestor@cliente-teste.com.br", "assunto": "Folha 10/2026",
              "html": "<p>Rubricas a parametrizar</p>", "tipo": "pendencia",
              "anexos": [{"nome": "rubricas.csv", "tipo": "text/csv", "conteudo_base64": base64.b64encode(b"8781;Ajuda").decode()}]}

    assert cliente.post(url, json=pedido, headers={"Authorization": "Bearer jbt_errado"}).status_code == 401
    recusado = cliente.post(url, json=pedido, headers=cab_job)
    assert recusado.status_code == 422 and "cliente-teste.com.br" in recusado.json()["motivo"] and carteiro.enviados == []

    assert cliente.post("/api/v1/emails/dominios", json={"dominio": "não é domínio"}).status_code == 422
    assert cliente.post("/api/v1/emails/dominios", json={"dominio": "@Cliente-Teste.com.br"}).json() == {"dominio": "cliente-teste.com.br"}
    assert "cliente-teste.com.br" in cliente.get("/api/v1/emails/configuracao").json()["dominios"]
    ruim = cliente.post(url, json={**pedido, "anexos": [{"nome": "x.exe", "conteudo_base64": "MQ=="}]}, headers=cab_job)
    assert ruim.status_code == 422 and "não permitido" in ruim.json()["erro"]

    enviado = cliente.post(url, json={**pedido, "chave_idempotencia": "folha-9101"}, headers=cab_job)
    assert enviado.status_code == 201 and enviado.json()["situacao"] == "enviado", enviado.text
    email_id = enviado.json()["email_id"]
    assert carteiro.enviados[0]["html"] == "<p>Rubricas a parametrizar</p>" and carteiro.enviados[0]["cc"] == ["gestor@cliente-teste.com.br"]
    assert carteiro.enviados[0]["anexos"] == [("rubricas.csv", "text/csv", b"8781;Ajuda")]
    repetido = cliente.post(url, json={**pedido, "chave_idempotencia": "folha-9101"}, headers=cab_job)
    assert repetido.json()["email_id"] == email_id and len(carteiro.enviados) == 1
    sessao.expire_all()
    assert sessao.execute(text("SELECT count(*) FROM email_anexos WHERE email_id = :e AND conteudo IS NOT NULL"),
                          {"e": email_id}).scalar() == 0  # enviado: o conteúdo do anexo sai

    # Falha definitiva e reenvio pela tela.
    carteiro.falhar = ErroDeEnvio("Microsoft Graph recusou o envio (HTTP 400)", temporario=False)
    falhou = cliente.post(url, json={**pedido, "assunto": "Outra"}, headers=cab_job).json()
    assert falhou["situacao"] == "falhou"
    carteiro.falhar = None
    assert cliente.post(f"/api/v1/emails/{falhou['email_id']}/reenviar").json()["situacao"] == "enviado"
    assert cliente.post(f"/api/v1/emails/{email_id}/reenviar").status_code == 422  # já enviado

    # A automação mandou pela máquina: só registra.
    maquina = cliente.post(f"{url}/registro", json={"para": ["analista@cliente-teste.com.br"], "assunto": "Folha (Outlook)",
                                                    "meio": "outlook", "anexos": ["folha.pdf"]}, headers=cab_job)
    assert maquina.status_code == 201 and maquina.json()["situacao"] == "enviado_pela_maquina"
    assert len(carteiro.enviados) == 2

    lista = cliente.get("/api/v1/emails", params={"automacao": admin.automation_id}).json()
    situacoes = sorted(e["situacao"] for e in lista["emails"])
    assert situacoes == ["enviado", "enviado", "enviado_pela_maquina", "recusado"]
    detalhe = cliente.get(f"/api/v1/emails/{email_id}").json()["email"]
    assert detalhe["html"] == "<p>Rubricas a parametrizar</p>" and detalhe["execucao_id"] == execution_id
    assert detalhe["anexos"] == [{"nome": "rubricas.csv", "tamanho": 10}] and detalhe["tipo"] == "pendencia"
    assert detalhe["automacao"]["id"] == admin.automation_id
    assert cliente.get("/api/v1/emails", params={"busca": "outlook"}).json()["emails"][0]["meio"] == "outlook"

    # E-mail de teste do Portal.
    assert cliente.post("/api/v1/emails/teste", json={"para": "ti@qualquer.com"}).json()["situacao"] == "enviado"

    # Execução encerrada: não pede mais.
    sessao.execute(text("UPDATE execution_attempts SET status = 'succeeded' WHERE id = :a"), {"a": tentativa})
    sessao.commit()
    assert cliente.post(url, json=pedido, headers=cab_job).status_code == 409
    assert cliente.delete("/api/v1/emails/dominios/cliente-teste.com.br").status_code == 204
    print("\ne-mail: domínio fora recusado e registrado; anexo e cópia pelo Graph; idempotência; falha e reenvio; "
          "máquina só registra; execução encerrada 409")
