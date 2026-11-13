"""SDK 0.5.0: e-mail pelo Portal.

- ``a.email()`` manda pelo Portal com o token do job: destinatários, cópia, anexos em base64;
- domínio recusado vira ``EmailRecusado``; Portal fora do ar, ``EmailIndisponivel``;
- campo oculto de segredo vira *** no assunto e no corpo;
- ``a.email_enviado_pela_maquina()`` só registra e nunca derruba a automação;
- modo desligado não manda nada; modo agente avisa que não leva e-mails.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import pytest

from portal_automacoes import Automacao, EmailIndisponivel, EmailRecusado
from portal_automacoes.eventos import validar
from portal_automacoes.fila import FilaLocal
from portal_automacoes.transporte import TransporteDesligado
from portal_automacoes.transporte_agente import TransporteAgente
from portal_automacoes.transporte_direto import TransporteDireto
from simuladores.portal_simulado import PortalSimulado


def _automacao(tmp_path: Path, transporte: Any, log: io.StringIO | None = None) -> Automacao:
    return Automacao(transporte, FilaLocal(tmp_path / "fila.db"), log_local=log or io.StringIO())


def test_email_pelo_portal_com_anexo_recusa_e_mascara(tmp_path: Path) -> None:
    anexo = tmp_path / "rubricas.csv"
    anexo.write_bytes(b"8781;Ajuda de custo")
    with PortalSimulado(None, None, validar) as portal:
        job = portal.criar_job("tsk_1", "jbt_1")
        job.segredos = {"dominio": {"usuario": "folha", "senha": "Senha-Secreta-99"}}
        job.ocultos = {"dominio": ["senha"]}
        job.dominios_permitidos = {"biason.net"}
        a = _automacao(tmp_path, TransporteDireto(portal.url, "tsk_1", "jbt_1", permitir_http=True))
        a.segredo("dominio")
        r = a.email("analista@biason.net", "Folha 10/2026", html="<p>senha Senha-Secreta-99 usuario folha</p>",
                    cc=["gestor@biason.net"], anexos=[anexo, ("resumo.txt", b"ok")], chave="folha-101")
        assert r == {"email_id": "eml_1", "situacao": "enviado"}
        pedido = job.emails[0]
        assert pedido["para"] == ["analista@biason.net"] and pedido["cc"] == ["gestor@biason.net"]
        assert pedido["html"] == "<p>senha *** usuario folha</p>" and pedido["chave_idempotencia"] == "folha-101"
        assert [(x["nome"], base64.b64decode(x["conteudo_base64"])) for x in pedido["anexos"]] == [
            ("rubricas.csv", b"8781;Ajuda de custo"), ("resumo.txt", b"ok")]
        assert pedido["anexos"][0]["tipo"] in ("text/csv", "application/vnd.ms-excel")
        with pytest.raises(EmailRecusado, match="domínio não permitido: cliente.com.br"):
            a.email("joao@cliente.com.br", "Folha", texto="x")
        with pytest.raises(EmailRecusado, match="2,5 MB"):
            a.email("analista@biason.net", "Grande", texto="x", anexos=[("grande.bin", b"0" * (3 * 1024 * 1024))])

        registro = a.email_enviado_pela_maquina("joao@cliente.com.br", "Folha (Outlook)", anexos=[anexo])
        assert registro["situacao"] == "enviado_pela_maquina"
        assert job.emails_da_maquina[0]["anexos"] == ["rubricas.csv"] and job.emails_da_maquina[0]["meio"] == "outlook"


def test_portal_fora_do_ar_e_modos(tmp_path: Path) -> None:
    log = io.StringIO()
    fora = _automacao(tmp_path, TransporteDireto("http://127.0.0.1:9", "tsk_1", "jbt_1", permitir_http=True, tempo_limite_s=1), log)
    with pytest.raises(EmailIndisponivel, match="Portal indisponível"):
        fora.email("a@biason.net", "x", texto="y")
    assert fora.email_enviado_pela_maquina("a@biason.net", "x")["situacao"] == "nao_registrado"  # não derruba
    assert "não ficou registrado" in log.getvalue()

    log2 = io.StringIO()
    desligado = _automacao(tmp_path / "d", TransporteDesligado(), log2)
    assert desligado.email("a@biason.net", "Teste local", texto="y")["situacao"] == "simulado"
    assert "não enviado" in log2.getvalue()
    agente = _automacao(tmp_path / "g", TransporteAgente("pipe", "token", tmp_path))
    with pytest.raises(EmailIndisponivel, match="modo agente"):
        agente.email("a@biason.net", "x", texto="y")
