"""SDK 0.5.0: segredos entregues pelo Portal.

- ``segredo()`` pede uma vez e guarda na memória; vários de uma vez num pedido só;
- o valor vira *** nos eventos (inclusive na fila local em disco) e no log local;
- negado, Portal fora do ar ou modo agente: ``SegredoIndisponivel`` com a chave e o motivo, sem valor;
- modo desligado: lê ``PORTAL_SEGREDO_<CHAVE>``;
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

from portal_automacoes import Automacao, SegredoIndisponivel
from portal_automacoes.fila import FilaLocal
from portal_automacoes.segredos import variavel_local
from portal_automacoes.transporte import FalhaDeTransporte, TransporteDesligado
from portal_automacoes.transporte_agente import TransporteAgente
from portal_automacoes.transporte_direto import TransporteDireto

SENHA = "Senha-Do-Banco-2026"


class Portal(TransporteDesligado):
    nome = "direto"

    def __init__(self, liberados: dict[str, str]) -> None:
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


def test_pede_uma_vez_guarda_na_memoria_e_mascara_eventos_e_log(tmp_path: Path) -> None:
    portal = Portal({"dominio.senha_banco": SENHA, "smtp.senha": "smtp-123456"})
    log = io.StringIO()
    a = _automacao(tmp_path, portal, log)
    assert a.segredo("Dominio.Senha_Banco") == SENHA  # chave normalizada como no Portal
    assert a.segredo("dominio.senha_banco") == SENHA
    assert a.segredos("dominio.senha_banco", "smtp.senha") == {"dominio.senha_banco": SENHA, "smtp.senha": "smtp-123456"}
    assert portal.pedidos == [["dominio.senha_banco"], ["smtp.senha"]]  # só o que faltava

    # Fila "fora do ar" para os eventos ficarem no disco e podermos ler o que foi gravado.
    portal.enviar = lambda eventos: (_ for _ in ()).throw(FalhaDeTransporte("fora do ar"))  # type: ignore[method-assign]
    with a:
        a.log(f"conectando com senha={SENHA}")
        a._avisar(f"falhou com {SENHA}")
    gravado = (tmp_path / "fila.db").read_bytes()
    assert SENHA.encode() not in gravado and b"senha=***" in gravado
    assert SENHA not in log.getvalue() and "falhou com ***" in log.getvalue()


def test_negado_e_fora_do_ar_levantam_sem_mostrar_valor(tmp_path: Path) -> None:
    portal = Portal({"dominio.senha_banco": SENHA})
    a = _automacao(tmp_path, portal)
    with pytest.raises(SegredoIndisponivel, match="smtp.senha: não existe ou não está liberado"):
        a.segredos("dominio.senha_banco", "smtp.senha")
    assert a.segredo("dominio.senha_banco") == SENHA  # o que veio fica guardado
    portal.fora_do_ar = True
    with pytest.raises(SegredoIndisponivel, match="Portal indisponível") as erro:
        a.segredo("outro.segredo")
    assert SENHA not in str(erro.value)
    with pytest.raises(ValueError):
        a.segredo("com espaço!")


def test_modo_desligado_le_do_ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert variavel_local("dominio.senha_banco") == "PORTAL_SEGREDO_DOMINIO_SENHA_BANCO"
    monkeypatch.setenv("PORTAL_SEGREDO_DOMINIO_SENHA_BANCO", "local-123")
    a = _automacao(tmp_path, TransporteDesligado())
    assert a.segredo("dominio.senha_banco") == "local-123"
    with pytest.raises(SegredoIndisponivel, match="PORTAL_SEGREDO_SMTP_SENHA"):
        a.segredo("smtp.senha")


def test_modo_agente_avisa_que_ainda_nao_entrega(tmp_path: Path) -> None:
    a = _automacao(tmp_path, TransporteAgente("pipe-teste", "token", tmp_path))
    with pytest.raises(SegredoIndisponivel, match="modo agente"):
        a.segredo("dominio.senha_banco")


def test_modo_direto_pede_com_o_token_no_cabecalho(tmp_path: Path) -> None:
    recebido: dict[str, Any] = {}

    class Receptor(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            recebido["caminho"] = self.path
            recebido["autorizacao"] = self.headers["Authorization"]
            recebido["corpo"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            corpo = json.dumps({"segredos": {"dominio.senha_banco": SENHA}, "negados": {}}).encode()
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
        assert _automacao(tmp_path, transporte).segredo("dominio.senha_banco") == SENHA
    finally:
        servidor.shutdown()
    assert recebido["caminho"] == "/api/v1/direto/jobs/tex_1/segredos"
    assert recebido["autorizacao"] == "Bearer jbt_segredo" and recebido["corpo"] == {"chaves": ["dominio.senha_banco"]}
