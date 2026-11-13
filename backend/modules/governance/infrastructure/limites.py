"""Leitura dos limites do sistema: o contrato que os outros contextos usam.

``ler_limite(db, chave)`` devolve o valor gravado (escopo global) ou, sem linha, o padrão do
catálogo. Valor gravado fora da faixa do catálogo (de antes da validação) é trazido para a faixa.
Limite de origem "arquivo" vem do ``.env``.

``limite_em_cache`` serve a quem não tem sessão de banco à mão (as conexões ao vivo): lê com
sessão própria e guarda por alguns segundos.
"""

from __future__ import annotations

import time
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from modules.governance.domain.configuracoes import limite
from modules.governance.infrastructure.orm.models import SystemLimitRecord

VALIDADE_DO_CACHE_S = 30.0
_cache: dict[str, tuple[float, int]] = {}
_trava = Lock()


def ler_limite(db: Session, chave: str) -> int:
    item = limite(chave)
    if item.origem == "arquivo":
        valor = getattr(get_settings(), (item.variavel_de_ambiente or "").lower(), None)
        return int(valor) if isinstance(valor, int) else item.padrao
    gravado = db.scalar(select(SystemLimitRecord.value).where(
        SystemLimitRecord.key == chave, SystemLimitRecord.organization_id.is_(None)).order_by(SystemLimitRecord.id).limit(1))
    if gravado is None:
        return item.padrao
    return min(max(int(gravado), item.minimo), item.maximo)


def ler_limite_em_bytes(db: Session, chave: str) -> int:
    """Para os limites em MB (pacote, arquivo)."""
    return ler_limite(db, chave) * 1024 * 1024


def limite_em_cache(chave: str) -> int:
    agora = time.monotonic()
    with _trava:
        guardado = _cache.get(chave)
        if guardado and agora - guardado[0] < VALIDADE_DO_CACHE_S:
            return guardado[1]
    from infrastructure.database import SessionLocal

    try:
        with SessionLocal() as db:
            valor = ler_limite(db, chave)
    except Exception:  # banco fora: não derruba a tela, vale o padrão
        valor = limite(chave).padrao
    with _trava:
        _cache[chave] = (agora, valor)
    return valor


def esquecer_cache() -> None:
    with _trava:
        _cache.clear()
