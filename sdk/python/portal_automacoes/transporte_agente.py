"""Modo agente: a automação fala só com o Agent local, por um named pipe da tentativa.

O ExecutionHost cria o pipe e entrega nome e token em AUTOMATION_EVENTS_PIPE e
AUTOMATION_EVENTS_TOKEN. O protocolo (contracts/automation-events/v1/README.md) é de
pergunta e resposta, numa thread só: no Windows, leitura e escrita síncronas no mesmo
handle se bloqueiam, então o SDK nunca deixa uma leitura pendurada.
"""

from __future__ import annotations

import _winapi
import json
import msvcrt
import shutil
import time
from pathlib import Path
from typing import Any, BinaryIO

from .transporte import FalhaDeTransporte, Recusado

ESPERA_PIPE_OCUPADO_S = 5.0
ESPERA_RESPOSTA_S = 30.0  # Agent que não responde não pode travar a automação
LIMITE_LINHA = 64 * 1024 + 1024


class TransporteAgente:
    nome = "agente"

    def __init__(self, pipe: str, token: str, pasta_imagens: Path) -> None:
        if not pipe or not token:
            raise ValueError("modo agente sem AUTOMATION_EVENTS_PIPE ou AUTOMATION_EVENTS_TOKEN")
        self._caminho = pipe if pipe.startswith("\\\\.\\pipe\\") else f"\\\\.\\pipe\\{pipe}"
        self._token = token
        self._pasta_imagens = pasta_imagens
        self._arquivo: BinaryIO | None = None
        self._buffer = b""
        self._comandos: list[dict[str, Any]] = []

    # -- conexão -----------------------------------------------------------
    def conectar(self) -> int:
        self.fechar()
        limite = time.monotonic() + ESPERA_PIPE_OCUPADO_S
        while True:
            try:
                self._arquivo = open(self._caminho, "r+b", buffering=0)  # noqa: SIM115 - vive enquanto a conexão
                break
            except OSError as exc:
                # 231 = ERROR_PIPE_BUSY: o ExecutionHost ainda está recriando o pipe.
                if getattr(exc, "winerror", None) == 231 and time.monotonic() < limite:
                    time.sleep(0.1)
                    continue
                raise FalhaDeTransporte(f"Agent local indisponível ({exc.__class__.__name__})") from exc
        self._buffer = b""
        self._escrever({"tipo": "ola", "token": self._token})
        resposta = self._ler_ate({"ok", "erro"})
        if resposta["tipo"] == "erro":
            self.fechar()
            raise Recusado(f"Agent recusou a conexão: {resposta.get('motivo')}")
        return int(resposta.get("ultima_sequencia") or 0)

    def email(self, dados: dict[str, Any]) -> dict[str, Any]:
        from .emails import EmailIndisponivel

        raise EmailIndisponivel("no modo agente o Agent ainda não leva e-mails ao Portal; use o modo direto")

    registrar_email = email

    def segredos(self, chaves: list[str]) -> dict[str, Any]:
        from .segredos import SegredoIndisponivel

        raise SegredoIndisponivel("no modo agente o Agent ainda não entrega segredos; use o modo direto")

    def fechar(self) -> None:
        if self._arquivo is not None:
            try:
                self._arquivo.close()
            except OSError:
                pass
        self._arquivo = None

    # -- eventos e comandos -------------------------------------------------
    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        confirmada = 0
        for evento in eventos:
            self._escrever({"tipo": "evento", "evento": evento})
            resposta = self._ler_ate({"ack", "erro"})
            if resposta["tipo"] == "erro":
                raise Recusado(f"Agent recusou o evento {evento['sequence']}: {resposta.get('motivo')}")
            confirmada = max(confirmada, int(resposta["sequencia"]))
        return confirmada

    def comandos(self) -> list[dict[str, Any]]:
        self._escrever({"tipo": "ping"})
        self._ler_ate({"pong"})
        pendentes, self._comandos = self._comandos, []
        return pendentes

    def enviar_imagem(self, imagem_id: str, jpeg: bytes) -> None:
        """A imagem fica na pasta de artefatos da tentativa; o Agent envia por HTTPS."""
        self._pasta_imagens.mkdir(parents=True, exist_ok=True)
        temporario = self._pasta_imagens / f"{imagem_id}.jpg.tmp"
        temporario.write_bytes(jpeg)
        temporario.replace(self._pasta_imagens / f"{imagem_id}.jpg")

    def enviar_arquivo(self, caminho: Path, nome: str, item: str | None, tipo: str) -> None:
        """Copia para a pasta de artefatos da tentativa; o Agent recolhe e envia ao Portal.
        Nome repetido ganha um número, para um arquivo não apagar o outro."""
        pasta = self._pasta_imagens.parent
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / nome
        base, extensao, n = destino.stem, destino.suffix, 2
        while destino.exists():
            destino = pasta / f"{base} ({n}){extensao}"
            n += 1
        temporario = destino.with_name(destino.name + ".tmp")
        shutil.copyfile(caminho, temporario)
        temporario.replace(destino)

    # -- linhas -------------------------------------------------------------
    def _escrever(self, mensagem: dict[str, Any]) -> None:
        if self._arquivo is None:
            raise FalhaDeTransporte("sem conexão com o Agent local")
        try:
            self._arquivo.write(json.dumps(mensagem, ensure_ascii=False).encode("utf-8") + b"\n")
        except OSError as exc:
            self.fechar()
            raise FalhaDeTransporte(f"conexão com o Agent caiu ({exc.__class__.__name__})") from exc

    def _ler_ate(self, tipos: set[str]) -> dict[str, Any]:
        """Lê até uma resposta de um dos ``tipos``, guardando os comandos que chegarem antes."""
        while True:
            mensagem = self._ler_linha()
            if mensagem.get("tipo") == "comando" and isinstance(mensagem.get("comando"), dict):
                self._comandos.append(mensagem["comando"])
                continue
            if mensagem.get("tipo") in tipos:
                return mensagem
            if mensagem.get("tipo") == "erro":
                raise Recusado(f"Agent respondeu erro: {mensagem.get('motivo')}")

    def _esperar_dados(self) -> None:
        """Leitura síncrona não tem tempo limite: espera os dados chegarem antes de ler."""
        assert self._arquivo is not None
        handle = msvcrt.get_osfhandle(self._arquivo.fileno())
        limite = time.monotonic() + ESPERA_RESPOSTA_S
        while True:
            try:
                disponiveis, _ = _winapi.PeekNamedPipe(handle, 0)
            except OSError as exc:
                self.fechar()
                raise FalhaDeTransporte(f"conexão com o Agent caiu ({exc.__class__.__name__})") from exc
            if disponiveis:
                return
            if time.monotonic() >= limite:
                self.fechar()
                raise FalhaDeTransporte(f"o Agent não respondeu em {ESPERA_RESPOSTA_S:.0f}s")
            time.sleep(0.005)

    def _ler_linha(self) -> dict[str, Any]:
        if self._arquivo is None:
            raise FalhaDeTransporte("sem conexão com o Agent local")
        while b"\n" not in self._buffer:
            self._esperar_dados()
            try:
                bloco = self._arquivo.read(4096)
            except OSError as exc:
                self.fechar()
                raise FalhaDeTransporte(f"conexão com o Agent caiu ({exc.__class__.__name__})") from exc
            if not bloco:
                self.fechar()
                raise FalhaDeTransporte("o Agent fechou a conexão")
            self._buffer += bloco
            if len(self._buffer) > LIMITE_LINHA:
                self.fechar()
                raise FalhaDeTransporte("resposta do Agent acima do limite")
        linha, self._buffer = self._buffer.split(b"\n", 1)
        return json.loads(linha.decode("utf-8"))
