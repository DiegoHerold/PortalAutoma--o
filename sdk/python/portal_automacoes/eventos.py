"""Montagem e validação dos eventos do contrato automation-events/v1.

O schema em ``contrato/`` é cópia de ``contracts/automation-events/v1``; um teste garante
que as duas cópias são idênticas.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

PROTOCOLO = "automation-events/1"
LIMITE_BYTES = 64 * 1024


class EventoInvalido(ValueError):
    """O evento montado pela automação não cumpre o contrato (erro de programação)."""


def _data_hora(valor: object) -> bool:
    if not isinstance(valor, str):
        return True
    if "T" not in valor:
        return False
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


@lru_cache(maxsize=2)
def _validador(nome: str) -> Draft202012Validator:
    texto = resources.files("portal_automacoes").joinpath("contrato", nome).read_text(encoding="utf-8")
    formatos = FormatChecker(formats=())
    formatos.checks("date-time")(_data_hora)
    return Draft202012Validator(json.loads(texto), format_checker=formatos)


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def montar(sequencia: int, tipo: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Evento completo, já validado. Campos ``None`` do payload são omitidos."""
    evento = {
        "protocol_version": PROTOCOLO,
        "event_id": str(uuid.uuid4()),
        "sequence": sequencia,
        "type": tipo,
        "occurred_at": agora(),
        "payload": {k: v for k, v in payload.items() if v is not None},
    }
    validar(evento)
    return evento


def validar(evento: dict[str, Any]) -> None:
    tamanho = len(json.dumps(evento, ensure_ascii=False).encode("utf-8"))
    if tamanho > LIMITE_BYTES:
        raise EventoInvalido(f"evento '{evento.get('type')}' com {tamanho} bytes, acima do limite de {LIMITE_BYTES}")
    erros = sorted(_validador("automation-event.schema.json").iter_errors(evento), key=lambda e: list(e.absolute_path))
    if erros:
        detalhe = "; ".join(f"{'/'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}" for e in erros[:3])
        raise EventoInvalido(f"evento '{evento.get('type')}' fora do contrato: {detalhe}")
    payload = evento["payload"]
    if evento["type"] == "progresso" and payload["atual"] > payload["total"]:
        raise EventoInvalido("progresso com atual maior que total")


def comando_valido(comando: Any) -> bool:
    return isinstance(comando, dict) and not any(_validador("automation-command.schema.json").iter_errors(comando))
