"""Teto de conexões ao vivo (SSE) abertas juntas: limite "realtime.max_sse_connections".

Toda resposta ``text/event-stream`` do Portal passa por ``responder_ao_vivo``. Cheio, o Portal
responde 503 com ``Retry-After`` e a tela tenta de novo sozinha (``frontend/src/lib/stream.ts``).
A contagem é por processo do Portal.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from threading import Lock

from fastapi.responses import JSONResponse, Response, StreamingResponse

from modules.governance.infrastructure.limites import limite_em_cache

CHAVE = "realtime.max_sse_connections"
ESPERA_S = 5


class _Contador:
    def __init__(self) -> None:
        self.abertas = 0
        self._trava = Lock()

    def entrar(self) -> None:
        with self._trava:
            self.abertas += 1

    def sair(self) -> None:
        with self._trava:
            self.abertas = max(0, self.abertas - 1)


conexoes = _Contador()


async def _contado(gerar: AsyncIterator[str]) -> AsyncIterator[str]:
    conexoes.entrar()
    try:
        async for parte in gerar:
            yield parte
    finally:
        conexoes.sair()


def responder_ao_vivo(gerar: AsyncIterator[str], cabecalhos: dict[str, str] | None = None) -> Response:
    if conexoes.abertas >= limite_em_cache(CHAVE):
        return JSONResponse(status_code=503, headers={"Retry-After": str(ESPERA_S)}, content={
            "code": "LIMITE_DE_CONEXOES", "message": "Muitas telas acompanhando ao mesmo tempo. Tentando de novo."})
    return StreamingResponse(_contado(gerar), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", **(cabecalhos or {})})
