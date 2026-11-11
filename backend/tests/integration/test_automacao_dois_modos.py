"""A mesma automação, sem mudar código, no modo agente e no modo direto.

Modo agente: Agent Service simulado + ExecutionHost.exe REAL + SDK (named pipe com token).
Modo direto: Portal simulado em HTTPS com CA própria + SDK.
Nos dois, cada evento passa pelo validador real do Portal (Telemetry), como no gateway.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[3]
SDK = RAIZ / "sdk" / "python"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

from modules.telemetry.infrastructure.adapters.payload_validation import DefaultEventPayloadValidator  # noqa: E402
from simuladores import certificados  # noqa: E402
from simuladores.agente_simulado import EXECUTION_HOST, AgenteSimulado, montar_pacote  # noqa: E402
from simuladores.portal_simulado import PortalSimulado  # noqa: E402

EXEMPLO = SDK / "simuladores" / "automacao_exemplo.py"
pytestmark = pytest.mark.skipif(not EXECUTION_HOST.is_file(), reason="ExecutionHost.exe não compilado (dotnet build)")


def _validar_no_portal(evento: dict[str, Any]) -> dict[str, Any]:
    gravado, _, _ = DefaultEventPayloadValidator().validate("automation.event", evento)
    return gravado


def _normalizar(eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tira o que muda de uma execução para outra: id do evento, horário e id da imagem."""
    saida = []
    for evento in eventos:
        payload = dict(evento["payload"])
        if "imagem_id" in payload:
            payload["imagem_id"] = "<imagem>"
        saida.append({"sequence": evento["sequence"], "type": evento["type"], "payload": payload})
    return saida


@pytest.fixture(scope="module")
def pacote(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return montar_pacote(tmp_path_factory.mktemp("pacote"), EXEMPLO)


@pytest.fixture(scope="module")
def modo_agente(pacote: Path, tmp_path_factory: pytest.TempPathFactory):
    pasta = tmp_path_factory.mktemp("agente")
    agente = AgenteSimulado(Path(sys.executable), pasta)
    resultado = agente.executar(pacote, "automacao_exemplo", {"PORTAL_FILA_DIR": str(pasta / "fila")})
    assert resultado.codigo_saida == 0, resultado.stdout_automacao
    gravados = [_validar_no_portal(e) for e in resultado.eventos]
    return resultado, gravados


@pytest.fixture(scope="module")
def modo_direto(pacote: Path, tmp_path_factory: pytest.TempPathFactory):
    pasta = tmp_path_factory.mktemp("direto")
    ca, cert, chave = certificados.gerar(pasta / "tls")
    with PortalSimulado(cert, chave, _validar_no_portal) as portal:
        portal.criar_job("job_direto_1", "token-do-job-direto")
        ambiente = {**os.environ, "PYTHONPATH": str(pacote), "PORTAL_MODO": "direto", "PORTAL_URL": portal.url,
                    "PORTAL_JOB_ID": "job_direto_1", "PORTAL_JOB_TOKEN": "token-do-job-direto",
                    "PORTAL_CA_ARQUIVO": str(ca), "PORTAL_FILA_DIR": str(pasta / "fila")}
        processo = subprocess.run([sys.executable, "-m", "automacao_exemplo"], env=ambiente, cwd=pasta,
                                  capture_output=True, text=True, timeout=120, check=False)
        assert processo.returncode == 0, processo.stderr
        job = portal.jobs["job_direto_1"]
        return processo, [_validar_no_portal(e) for e in job.eventos], job


def test_modo_agente_entrega_todos_os_eventos_pelo_executionhost_real(modo_agente) -> None:
    resultado, gravados = modo_agente
    tipos = [e["type"] for e in gravados]
    assert tipos[0] == "execucao.iniciada" and tipos[-1] == "execucao.concluida"
    assert [e["sequence"] for e in gravados] == list(range(1, len(gravados) + 1))
    assert all(l["payload"]["events"][0]["event_type"] == "automation.event" for l in resultado.lotes)
    print(f"\nmodo agente: {len(gravados)} eventos via ExecutionHost.exe; tipos: {sorted(set(tipos))}")


def test_modo_agente_imagens_ficam_nos_artefatos_com_o_id_do_evento(modo_agente) -> None:
    resultado, gravados = modo_agente
    ids = [e["payload"]["imagem_id"] for e in gravados if e["type"] == "passo" and "imagem_id" in e["payload"]]
    assert ids
    for imagem_id in ids:
        assert (resultado.pasta_artefatos / "passos" / f"{imagem_id}.jpg").read_bytes()[:2] == b"\xff\xd8"


def test_modo_direto_entrega_eventos_e_imagens_por_https(modo_direto) -> None:
    processo, gravados, job = modo_direto
    assert job.recusados == []
    ids = [e["payload"]["imagem_id"] for e in gravados if e["type"] == "passo" and "imagem_id" in e["payload"]]
    assert ids and set(ids) == set(job.imagens)
    assert "pendentes=0 recusados=0" in processo.stderr
    print(f"\nmodo direto: {len(gravados)} eventos e {len(job.imagens)} imagens por HTTPS")


def test_cenario_17_mesmos_eventos_nos_dois_modos(modo_agente, modo_direto) -> None:
    _, agente = modo_agente
    _, direto, _ = modo_direto
    assert _normalizar(agente) == _normalizar(direto)
    print(f"\ncenário 17: {len(agente)} eventos idênticos nos dois modos (sem id, horário e id de imagem)")


def test_segredo_no_log_e_removido_antes_de_gravar_nos_dois_modos(modo_agente, modo_direto) -> None:
    for gravados in (modo_agente[1], modo_direto[1]):
        textos = [e["payload"]["texto"] for e in gravados if e["type"] == "log"]
        assert any("senha=***" in t for t in textos)
        assert not any("NaoDeveAparecer" in t for t in textos)
