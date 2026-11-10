"""Servidor de named pipe só com a biblioteca padrão (_winapi), para o Agent Service simulado."""

from __future__ import annotations

import _winapi

PIPE_ACCESS_DUPLEX = 0x00000003  # o PipeClient do ExecutionHost abre InOut
PIPE_TYPE_BYTE_WAIT = 0x00000000
ERROR_PIPE_CONNECTED = 535


class ServidorPipe:
    """Uma conexão. O ExecutionHost abre em leitura e escrita, mas só escreve; o Agent Service lê."""

    def __init__(self, nome: str) -> None:
        self.caminho = f"\\\\.\\pipe\\{nome}"
        self._handle = _winapi.CreateNamedPipe(
            self.caminho, PIPE_ACCESS_DUPLEX, PIPE_TYPE_BYTE_WAIT, 1, 65536, 65536, 0, _winapi.NULL)
        self._buffer = b""

    def aceitar(self) -> None:
        try:
            _winapi.ConnectNamedPipe(self._handle, False)
        except OSError as exc:
            if getattr(exc, "winerror", None) != ERROR_PIPE_CONNECTED:
                raise

    def linhas(self):
        """Gera as linhas até o cliente fechar."""
        while True:
            while b"\n" in self._buffer:
                linha, self._buffer = self._buffer.split(b"\n", 1)
                yield linha.decode("utf-8").rstrip("\r")
            try:
                dados, _ = _winapi.ReadFile(self._handle, 65536, False)
            except (BrokenPipeError, OSError):
                return
            if not dados:
                return
            self._buffer += dados

    def fechar(self) -> None:
        try:
            _winapi.CloseHandle(self._handle)
        except OSError:
            pass
