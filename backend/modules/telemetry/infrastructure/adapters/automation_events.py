"""Validação dos eventos da automação pelo contrato contracts/automation-events/v1.

O schema é lido do próprio diretório contracts/: Portal, Agent e SDK usam o mesmo
arquivo, sem cópia divergente. O Portal é quem valida o contrato inteiro; o Agent só
faz a conferência mínima.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from modules.telemetry.domain.errors import TelemetryValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[5] / "contracts" / "automation-events" / "v1" / "automation-event.schema.json"
MAX_EVENT_BYTES = 64 * 1024
LEVELS = {"debug": "DEBUG", "info": "INFO", "aviso": "WARNING", "erro": "ERROR", "critico": "CRITICAL"}

# Segredos que aparecem no texto do log ("senha=abc", "Bearer xyz"). O mascaramento por
# chave (RecursiveSecretMasker) não alcança texto livre.
_SEGREDO_ATRIBUIDO = re.compile(
    r"(?i)\b(senha|password|passwd|pwd|token|secret|segredo|api[_-]?key|client[_-]?secret)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")


def _data_hora(valor: object) -> bool:
    """date-time RFC 3339 com fuso. Sem isto o jsonschema não confere o formato
    (ele depende de um pacote opcional)."""
    if not isinstance(valor, str) or "T" not in valor:
        return True if not isinstance(valor, str) else False
    try:
        data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return False
    return data.tzinfo is not None


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    formatos = FormatChecker(formats=())
    formatos.checks("date-time")(_data_hora)
    return Draft202012Validator(schema, format_checker=formatos)


def validate_automation_event(event: Any) -> dict[str, Any]:
    """Confere o evento pelo schema e pelas regras que o schema não expressa.
    Levanta TelemetryValidationError com todos os erros encontrados."""
    if not isinstance(event, dict):
        raise TelemetryValidationError("automation.event: o payload precisa ser um objeto.")
    size = len(json.dumps(event, ensure_ascii=False).encode("utf-8"))
    if size > MAX_EVENT_BYTES:
        raise TelemetryValidationError(f"automation.event: {size} bytes, acima do limite de {MAX_EVENT_BYTES}.")
    errors = sorted(_validator().iter_errors(event), key=lambda e: list(e.absolute_path))
    if errors:
        detalhes = "; ".join(f"{'/'.join(str(p) for p in e.absolute_path) or '(raiz)'}: {e.message}" for e in errors[:5])
        raise TelemetryValidationError(f"automation.event fora do contrato: {detalhes}")
    payload = event["payload"]
    if event["type"] == "progresso" and payload["atual"] > payload["total"]:
        raise TelemetryValidationError("automation.event: progresso com atual maior que total.")
    return event


def scrub_text(text: str) -> str:
    """Remove segredos de texto livre antes de gravar."""
    text = _SEGREDO_ATRIBUIDO.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return _BEARER.sub(lambda m: f"{m.group(1)} ***", text)


def scrub_automation_event(event: dict[str, Any]) -> dict[str, Any]:
    """Cópia do evento com o texto do log sem segredos."""
    if event.get("type") != "log":
        return event
    payload = dict(event["payload"])
    payload["texto"] = scrub_text(payload["texto"])
    return {**event, "payload": payload}


def message_and_level(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """Texto e nível que vão para as colunas de busca de execution_events."""
    payload = event["payload"]
    kind = event["type"]
    if kind == "log":
        return payload["texto"], LEVELS[payload["nivel"]]
    if kind == "passo":
        return payload["rotulo"], None
    if kind == "atencao":
        return payload["motivo"], "WARNING"
    if kind == "progresso":
        return payload.get("rotulo") or f"{payload['atual']} de {payload['total']}", None
    if kind in {"etapa.iniciada", "etapa.concluida"}:
        return payload["etapa"], "ERROR" if payload.get("situacao") == "erro" else None
    if kind in {"item.iniciado", "item.concluido"}:
        return payload.get("resumo") or payload.get("rotulo") or payload["item"], "ERROR" if payload.get("situacao") == "erro" else None
    return None, None
