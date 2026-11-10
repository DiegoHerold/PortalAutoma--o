"""Contrato automation-events/v1 no Portal: exemplos, validação e remoção de segredos."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from modules.telemetry.domain.errors import TelemetryValidationError
from modules.telemetry.infrastructure.adapters.automation_events import (
    MAX_EVENT_BYTES,
    SCHEMA_PATH,
    scrub_text,
    validate_automation_event,
)
from modules.telemetry.infrastructure.adapters.payload_validation import DefaultEventPayloadValidator

EXEMPLOS = SCHEMA_PATH.parent / "examples"
VALIDOS = json.loads((EXEMPLOS / "validos.json").read_text(encoding="utf-8"))
INVALIDOS = json.loads((EXEMPLOS / "invalidos.json").read_text(encoding="utf-8"))
TIPOS = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["type"]["enum"]


def test_os_exemplos_validos_cobrem_todos_os_tipos() -> None:
    assert {e["evento"]["type"] for e in VALIDOS} == set(TIPOS)


@pytest.mark.parametrize("exemplo", VALIDOS, ids=[e["descricao"] for e in VALIDOS])
def test_exemplo_valido_passa(exemplo: dict) -> None:
    assert validate_automation_event(deepcopy(exemplo["evento"])) == exemplo["evento"]


@pytest.mark.parametrize("exemplo", INVALIDOS, ids=[e["descricao"] for e in INVALIDOS])
def test_exemplo_invalido_e_recusado(exemplo: dict) -> None:
    with pytest.raises(TelemetryValidationError):
        validate_automation_event(deepcopy(exemplo["evento"]))


def _evento(tipo: str, payload: dict) -> dict:
    return {"protocol_version": "automation-events/1", "event_id": "0b6f6a52-3f0e-4b8e-9b55-7c1c7d1f0c01",
            "sequence": 1, "type": tipo, "occurred_at": "2026-11-09T14:00:00Z", "payload": payload}


def test_progresso_com_atual_maior_que_total_e_recusado() -> None:
    with pytest.raises(TelemetryValidationError, match="atual maior que total"):
        validate_automation_event(_evento("progresso", {"atual": 51, "total": 50}))


def test_evento_acima_do_limite_e_recusado_sem_validar_o_resto() -> None:
    linhas = [{"descricao": "x" * 400} for _ in range(200)]
    evento = _evento("atencao", {"item": "5066", "motivo": "m", "tabela": {"colunas": [{"chave": "descricao", "titulo": "D"}], "linhas": linhas}})
    assert len(json.dumps(evento).encode()) > MAX_EVENT_BYTES
    with pytest.raises(TelemetryValidationError, match="acima do limite"):
        validate_automation_event(evento)


def test_schema_vem_do_diretorio_contracts() -> None:
    assert SCHEMA_PATH.parts[-4:] == ("contracts", "automation-events", "v1", "automation-event.schema.json")
    assert SCHEMA_PATH.is_file()


@pytest.mark.parametrize("texto,esperado", [
    ("login com senha=Abc123 ok", "login com senha=*** ok"),
    ("password: 'p@ss w0rd'", "password: ***"),
    ("Authorization Bearer eyJhbGciOiJIUzI1NiJ9.abc", "Authorization Bearer ***"),
    ("api_key=XYZ987", "api_key=***"),
    ("Empresa 5066 carregada em 22s", "Empresa 5066 carregada em 22s"),
])
def test_segredos_no_texto_do_log_sao_removidos(texto: str, esperado: str) -> None:
    assert scrub_text(texto) == esperado


def test_validador_do_portal_aceita_automation_event_e_extrai_texto_e_nivel() -> None:
    evento = _evento("log", {"nivel": "aviso", "texto": "senha=segredo123 recusada", "espera": False})

    payload, nivel, mensagem = DefaultEventPayloadValidator().validate("automation.event", evento)

    assert nivel == "WARNING"
    assert mensagem == "senha=*** recusada"
    assert payload["payload"]["texto"] == "senha=*** recusada"
    assert evento["payload"]["texto"] == "senha=segredo123 recusada"  # o original não é alterado


def test_validador_do_portal_recusa_automation_event_fora_do_contrato() -> None:
    with pytest.raises(TelemetryValidationError, match="fora do contrato"):
        DefaultEventPayloadValidator().validate("automation.event", _evento("passo", {"rotulo": "Abriu"}))


def test_schema_do_lote_portal_agent_aceita_automation_event() -> None:
    raiz = Path(SCHEMA_PATH).parents[2]
    schema = json.loads((raiz / "events" / "execution-event.schema.json").read_text(encoding="utf-8"))
    assert "automation.event" in schema["properties"]["event_type"]["enum"]
