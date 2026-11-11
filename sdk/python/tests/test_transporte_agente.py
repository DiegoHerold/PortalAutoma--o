"""Modo agente contra um ExecutionHost de mentira que responde errado ou fica mudo.

O caminho feliz com o ExecutionHost.exe real está em
backend/tests/integration/test_automacao_dois_modos.py.
"""

from __future__ import annotations

import _winapi
import json
import threading
import uuid

import pytest

from portal_automacoes import transporte_agente
from portal_automacoes.transporte import FalhaDeTransporte, Recusado
from portal_automacoes.transporte_agente import TransporteAgente


class HostDeMentira:
    def __init__(self, respostas: dict[str, dict | None]) -> None:
        self.nome = f"teste-sdk-{uuid.uuid4().hex}"
        self._respostas = respostas
        self._handle = _winapi.CreateNamedPipe(f"\\\\.\\pipe\\{self.nome}", 0x3, 0, 1, 65536, 65536, 0, _winapi.NULL)
        threading.Thread(target=self._rodar, daemon=True).start()

    def _rodar(self) -> None:
        try:
            _winapi.ConnectNamedPipe(self._handle, False)
        except OSError:
            pass
        buffer = b""
        while True:
            try:
                dados, _ = _winapi.ReadFile(self._handle, 65536, False)
            except OSError:
                return
            buffer += dados
            while b"\n" in buffer:
                linha, buffer = buffer.split(b"\n", 1)
                resposta = self._respostas.get(json.loads(linha)["tipo"])
                if resposta is not None:
                    _winapi.WriteFile(self._handle, json.dumps(resposta).encode() + b"\n", False)


def test_token_recusado_pelo_agent(tmp_path) -> None:
    host = HostDeMentira({"ola": {"tipo": "erro", "motivo": "token_invalido"}})
    with pytest.raises(Recusado, match="token_invalido"):
        TransporteAgente(host.nome, "token-errado", tmp_path).conectar()


def test_erro_em_vez_de_pong_nao_trava(tmp_path) -> None:
    host = HostDeMentira({"ola": {"tipo": "ok", "ultima_sequencia": 0}, "ping": {"tipo": "erro", "motivo": "mensagem_desconhecida"}})
    transporte = TransporteAgente(host.nome, "t", tmp_path)
    transporte.conectar()
    with pytest.raises(Recusado, match="mensagem_desconhecida"):
        transporte.comandos()


def test_agent_mudo_nao_trava_a_automacao(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(transporte_agente, "ESPERA_RESPOSTA_S", 0.5)
    host = HostDeMentira({"ola": {"tipo": "ok", "ultima_sequencia": 0}, "ping": None})
    transporte = TransporteAgente(host.nome, "t", tmp_path)
    transporte.conectar()
    with pytest.raises(FalhaDeTransporte, match="não respondeu"):
        transporte.comandos()


def test_comando_recebido_fica_guardado_mesmo_se_o_pong_nao_vier(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(transporte_agente, "ESPERA_RESPOSTA_S", 0.5)
    comando = {"protocol_version": "automation-events/1", "command_id": "cmd_1", "type": "parar_apos_item",
               "issued_at": "2026-11-09T14:00:00Z"}
    host = HostDeMentira({"ola": {"tipo": "ok", "ultima_sequencia": 0}, "ping": {"tipo": "comando", "comando": comando}})
    transporte = TransporteAgente(host.nome, "t", tmp_path)
    transporte.conectar()

    with pytest.raises(FalhaDeTransporte):
        transporte.comandos()
    assert transporte._comandos == [comando]
