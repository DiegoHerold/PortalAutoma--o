"""Tempo real entre processos com ``LISTEN/NOTIFY`` do PostgreSQL.

O aviso é só um gatilho: leva o id da execução (ou nada, no caso da fila). Quem recebe
relê o banco a partir do último evento visto, então nada se perde se um aviso faltar
(ADR-004: o banco é a fonte da verdade; o canal é transporte). Funciona com a API, o
worker e o beat em processos diferentes, ao contrário do publicador em memória.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text

from modules.telemetry.application.dto import ExecutionEventDTO, TelemetrySummaryDTO

logger = logging.getLogger(__name__)

CANAL_EXECUCAO = "portal_execucao"
CANAL_FILA = "portal_fila"
CANAIS = (CANAL_EXECUCAO, CANAL_FILA)


_motor: Any = None


def usar_motor(motor: Any) -> None:
    """Troca o banco do aviso e da escuta (os testes usam o banco deles). None volta ao padrão."""
    global _motor
    _motor = motor


def _motor_atual() -> Any:
    from infrastructure.database import engine

    return _motor if _motor is not None else engine


def notificar(canal: str, chave: str = "") -> None:
    """Avisa os ouvintes. Falha no aviso nunca derruba quem gravou: o stream relê sozinho."""
    try:
        with _motor_atual().connect() as conexao:
            conexao.execute(text("SELECT pg_notify(:canal, :chave)"), {"canal": canal, "chave": chave[:200]})
            conexao.commit()
    except Exception:  # noqa: BLE001 - transporte; o banco já tem o dado
        logger.warning("pg_notify falhou em %s", canal, exc_info=True)


class PostgresNotifyPublisher:
    """Mesma interface do publicador antigo; um aviso por lote de eventos."""

    def publish_execution_event(self, execution_id: str, event: ExecutionEventDTO) -> None:
        return None  # o resumo do lote avisa uma vez só

    def publish_execution_summary(self, summary: TelemetrySummaryDTO) -> None:
        notificar(CANAL_EXECUCAO, summary.execution_id)


class Ouvinte:
    """Uma conexão ``LISTEN`` por processo da API, numa thread própria (o psycopg assíncrono
    não roda no laço padrão do Windows). Os avisos chegam aos streams pelo laço deles."""

    def __init__(self) -> None:
        self._assinantes: dict[tuple[str, str], set[tuple[asyncio.Event, asyncio.AbstractEventLoop]]] = {}
        self._trava = threading.Lock()
        self._thread: threading.Thread | None = None
        self.conectado = False

    def _garantir_iniciado(self) -> None:
        with self._trava:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._escutar, name="portal-listen", daemon=True)
                self._thread.start()

    @contextlib.asynccontextmanager
    async def assinar(self, canal: str, chave: str = "") -> AsyncIterator[asyncio.Event]:
        self._garantir_iniciado()
        sinal = asyncio.Event()
        item = (sinal, asyncio.get_running_loop())
        with self._trava:
            self._assinantes.setdefault((canal, chave), set()).add(item)
        try:
            yield sinal
        finally:
            with self._trava:
                grupo = self._assinantes.get((canal, chave))
                if grupo is not None:
                    grupo.discard(item)
                    if not grupo:
                        self._assinantes.pop((canal, chave), None)

    def _avisar(self, canal: str | None = None, chave: str | None = None) -> None:
        with self._trava:
            if canal is None:
                alvos = [item for grupo in self._assinantes.values() for item in grupo]
            else:
                # ("*", "*") recebe tudo: o Painel acorda com qualquer execução ou com a fila.
                alvos = list(self._assinantes.get((canal, chave or ""), ())) + list(self._assinantes.get(("*", "*"), ()))
        for sinal, laco in alvos:
            with contextlib.suppress(RuntimeError):  # laço já fechado
                laco.call_soon_threadsafe(sinal.set)

    def _escutar(self) -> None:
        import psycopg

        espera = 1.0
        while True:
            try:
                url = _motor_atual().url  # o mesmo banco onde os avisos são enviados
                with psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password,
                                     dbname=url.database, autocommit=True, connect_timeout=10) as conexao:
                    for canal in CANAIS:
                        conexao.execute(f"LISTEN {canal}")
                    self.conectado, espera = True, 1.0
                    self._avisar()  # o que chegou enquanto estava fora é relido
                    while True:
                        for aviso in conexao.notifies(timeout=5.0):
                            self._avisar(aviso.channel, aviso.payload)
            except Exception:  # noqa: BLE001 - reconecta; os streams seguem com a releitura periódica
                logger.warning("LISTEN caiu; reconectando em %.0fs", espera, exc_info=True)
            self.conectado = False
            time.sleep(espera)
            espera = min(espera * 2, 30.0)


ouvinte = Ouvinte()


async def esperar_aviso(sinal: asyncio.Event, segundos: float) -> bool:
    """True se chegou aviso; False se passou o tempo (o stream relê do mesmo jeito)."""
    try:
        await asyncio.wait_for(sinal.wait(), timeout=segundos)
        return True
    except asyncio.TimeoutError:
        return False
    finally:
        sinal.clear()


def descrever(ouvinte_: Ouvinte) -> dict[str, Any]:
    with ouvinte_._trava:
        return {"conectado": ouvinte_.conectado, "assinaturas": sum(len(g) for g in ouvinte_._assinantes.values())}
