"""SDK 0.5.0: segredos entregues pelo Portal, com campos.

- ``segredo(chave)`` devolve os campos (``Segredo``); ``segredo(chave, campo)``, um valor;
- pede uma vez e guarda na memória; vários de uma vez num pedido só;
- só os campos ocultos viram *** nos eventos (inclusive na fila local em disco) e no log local;
- negado, Portal fora do ar ou modo agente: ``SegredoIndisponivel`` com a chave e o motivo, sem valor;
- modo desligado: ``PORTAL_SEGREDO_<CHAVE>`` (JSON) ou ``PORTAL_SEGREDO_<CHAVE>__<CAMPO>``;
- modo direto: ``POST .../segredos`` com o token do job no cabeçalho.
"""

from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from portal_automacoes import Automacao, Segredo, SegredoIndisponivel
from portal_automacoes.fila import FilaLocal
from portal_automacoes.segredos import variavel_local
from portal_automacoes.transporte import FalhaDeTransporte, TransporteDesligado
from portal_automacoes.transporte_agente import TransporteAgente
from portal_automacoes.transporte_direto import TransporteDireto

SENHA = "Senha-Do-Banco-2026"
DOMINIO = {"campos": {"usuario": "folha", "senha": SENHA, "banco": "contabil"}, "ocultos": ["senha"]}


class Portal(TransporteDesligado):
    nome = "direto"

    def __init__(self, liberados: dict[str, Any]) -> None:
        self.liberados = liberados
        self.pedidos: list[list[str]] = []
        self.fora_do_ar = False

    def segredos(self, chaves: list[str]) -> dict[str, Any]:
        self.pedidos.append(chaves)
        if self.fora_do_ar:
            raise FalhaDeTransporte("fora do ar")
        return {"segredos": {c: self.liberados[c] for c in chaves if c in self.liberados},
                "negados": {c: "não existe ou não está liberado para esta automação" for c in chaves if c not in self.liberados}}


def _automacao(tmp_path: Path, transporte: Any, log: io.StringIO | None = None) -> Automacao:
    return Automacao(transporte, FilaLocal(tmp_path / "fila.db"), log_local=log or io.StringIO())


def test_campos_um_pedido_so_e_so_o_oculto_mascarado(tmp_path: Path) -> None:
    portal = Portal({"dominio": DOMINIO, "smtp": {"campos": {"senha": "smtp-123456"}, "ocultos": ["senha"]}})
    log = io.StringIO()
    a = _automacao(tmp_path, portal, log)
    dominio = a.segredo("Dominio")  # chave normalizada como no Portal
    assert isinstance(dominio, Segredo) and dict(dominio) == DOMINIO["campos"]
    assert a.segredo("dominio", "senha") == SENHA and dominio.get("porta") is None
    assert SENHA not in repr(dominio) and repr(dominio) == "Segredo(dominio: usuario, senha, banco)"
    with pytest.raises(KeyError, match="não tem o campo 'porta' \\(tem: usuario, senha, banco\\)"):
        a.segredo("dominio", "porta")
    assert set(a.segredos("dominio", "smtp")) == {"dominio", "smtp"}
    assert portal.pedidos == [["dominio"], ["smtp"]]  # só o que faltava

    portal.enviar = lambda eventos: (_ for _ in ()).throw(FalhaDeTransporte("fora do ar"))  # type: ignore[method-assign]
    with a:
        a.log(f"login folha / {SENHA} no banco contabil")
        a._avisar(f"falhou com {SENHA}")
    gravado = (tmp_path / "fila.db").read_bytes()
    assert SENHA.encode() not in gravado and "login folha / *** no banco contabil".encode() in gravado
    assert SENHA not in log.getvalue() and "falhou com ***" in log.getvalue()


def test_negado_e_fora_do_ar_levantam_sem_mostrar_valor(tmp_path: Path) -> None:
    portal = Portal({"dominio": DOMINIO})
    a = _automacao(tmp_path, portal)
    with pytest.raises(SegredoIndisponivel, match="smtp: não existe ou não está liberado"):
        a.segredos("dominio", "smtp")
    assert a.segredo("dominio", "senha") == SENHA  # o que veio fica guardado
    portal.fora_do_ar = True
    with pytest.raises(SegredoIndisponivel, match="Portal indisponível") as erro:
        a.segredo("outro")
    assert SENHA not in str(erro.value)
    with pytest.raises(ValueError):
        a.segredo("com espaço!")


def test_modo_desligado_le_do_ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert variavel_local("dominio") == "PORTAL_SEGREDO_DOMINIO"
    monkeypatch.setenv("PORTAL_SEGREDO_DOMINIO", json.dumps({"usuario": "u", "senha": "local-123"}))
    monkeypatch.setenv("PORTAL_SEGREDO_SMTP__SENHA", "smtp-local")
    a = _automacao(tmp_path, TransporteDesligado())
    assert dict(a.segredo("dominio")) == {"usuario": "u", "senha": "local-123"}
    assert dict(a.segredo("smtp")) == {"senha": "smtp-local"}
    with pytest.raises(SegredoIndisponivel, match="PORTAL_SEGREDO_ERP"):
        a.segredo("erp")


def test_modo_agente_avisa_que_ainda_nao_entrega(tmp_path: Path) -> None:
    a = _automacao(tmp_path, TransporteAgente("pipe-teste", "token", tmp_path))
    with pytest.raises(SegredoIndisponivel, match="modo agente"):
        a.segredo("dominio")


def test_modo_direto_pede_com_o_token_no_cabecalho(tmp_path: Path) -> None:
    recebido: dict[str, Any] = {}

    class Receptor(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            recebido["caminho"] = self.path
            recebido["autorizacao"] = self.headers["Authorization"]
            recebido["corpo"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            corpo = json.dumps({"segredos": {"dominio": DOMINIO}, "negados": {}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_: Any) -> None:
            return None

    servidor = HTTPServer(("127.0.0.1", 0), Receptor)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        transporte = TransporteDireto(f"http://127.0.0.1:{servidor.server_port}", "tex_1", "jbt_segredo", permitir_http=True)
        assert _automacao(tmp_path, transporte).segredo("dominio", "banco") == "contabil"
    finally:
        servidor.shutdown()
    assert recebido["caminho"] == "/api/v1/direto/jobs/tex_1/segredos"
    assert recebido["autorizacao"] == "Bearer jbt_segredo" and recebido["corpo"] == {"chaves": ["dominio"]}
