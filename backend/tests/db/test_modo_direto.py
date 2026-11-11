"""Modo direto real no Portal: credencial do job, limites e auditoria (cenários 13, 14 e 15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from tests.db.semente import (
    Roteiro,
    agente,
    automacao,
    execucao,
    instancia_direta,
    maquina,
    tentativa_agente,
    tentativa_direta,
)

DIA = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def job(sessao):
    automation_id, version_id = automacao(sessao)
    mch = maquina(sessao)
    instancia = instancia_direta(sessao, automation_id, mch)
    _, job_id = execucao(sessao, version_id, DIA)
    attempt_id, token = tentativa_direta(sessao, job_id, instancia, mch)
    return {"automation_id": automation_id, "version_id": version_id, "machine": mch, "instancia": instancia,
            "job_id": job_id, "attempt_id": attempt_id, "token": token}


def _post(cliente, job_id: str, token: str | None, corpo: dict | bytes, tipo: str = "application/json"):
    cabecalhos = {"Content-Type": tipo}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    if isinstance(corpo, bytes):
        return cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", content=corpo, headers=cabecalhos)
    return cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json=corpo, headers=cabecalhos)


def _auditorias(sessao, job_id: str) -> list[str]:
    sessao.expire_all()
    return [r.metadata_json["motivo"] for r in sessao.execute(text(
        "SELECT metadata AS metadata_json FROM audit_events WHERE resource_type = 'job' AND resource_id = :j ORDER BY occurred_at"),
        {"j": job_id})]


def _log(n: int = 1):
    return Roteiro(DIA).emitir("execucao.iniciada").emitir("log", nivel="info", texto="Abrindo a Domínio").eventos[:n + 1]


def test_job_com_token_valido_recebe_eventos_e_estado(cliente, sessao, job) -> None:
    resposta = _post(cliente, job["job_id"], job["token"], {"eventos": _log()})
    assert resposta.status_code == 200 and resposta.json() == {"ultima_sequencia": 2, "recusados": []}
    estado = cliente.get(f"/api/v1/direto/jobs/{job['job_id']}/eventos/estado",
                         headers={"Authorization": f"Bearer {job['token']}"})
    assert estado.json() == {"ultima_sequencia": 2}
    executor = sessao.execute(text("SELECT DISTINCT executor_type, executor_id, agent_id FROM execution_events"
                                   " WHERE execution_attempt_id = :a"), {"a": job["attempt_id"]}).all()
    assert executor == [("direct", job["instancia"], None)]


def test_reenvio_nao_duplica(cliente, sessao, job) -> None:
    eventos = _log()
    _post(cliente, job["job_id"], job["token"], {"eventos": eventos})
    segunda = _post(cliente, job["job_id"], job["token"], {"eventos": eventos})
    assert segunda.status_code == 200
    total = sessao.execute(text("SELECT count(*) FROM execution_events WHERE execution_attempt_id = :a"),
                           {"a": job["attempt_id"]}).scalar_one()
    assert total == 2


def test_cenario_13_token_de_outro_job_e_recusado_e_auditado(cliente, sessao, job) -> None:
    _, outro_job = execucao(sessao, job["version_id"], DIA)
    resposta = _post(cliente, outro_job, job["token"], {"eventos": _log()})
    assert resposta.status_code == 401
    assert _auditorias(sessao, outro_job) == ["token_de_outro_job"]
    print(f"\ncenário 13: token do job {job['job_id'][:12]}… usado no job {outro_job[:12]}… -> 401, auditado")


def test_cenario_13_token_vencido_e_recusado_e_auditado(cliente, sessao, job) -> None:
    _, job_id = execucao(sessao, job["version_id"], DIA)
    _, vencido = tentativa_direta(sessao, job_id, job["instancia"], job["machine"], duracao=timedelta(seconds=-1))
    resposta = _post(cliente, job_id, vencido, {"eventos": _log()})
    assert resposta.status_code == 401
    assert _auditorias(sessao, job_id) == ["token_vencido"]


@pytest.mark.parametrize("token", [None, "jbt_inventado"])
def test_sem_token_ou_token_inventado_e_recusado(cliente, sessao, job, token) -> None:
    assert _post(cliente, job["job_id"], token, {"eventos": _log()}).status_code == 401
    assert _auditorias(sessao, job["job_id"])[-1] in ("token_ausente", "token_invalido")


def test_token_nunca_na_url(cliente, job) -> None:
    resposta = cliente.post(f"/api/v1/direto/jobs/{job['job_id']}/eventos?token={job['token']}", json={"eventos": _log()})
    assert resposta.status_code == 401


def test_cenario_14_instancia_revogada_nao_envia_mais_nada(cliente, sessao, job) -> None:
    sessao.execute(text("UPDATE direct_instances SET status = 'revogada', revoked_at = now() WHERE id = :i"),
                   {"i": job["instancia"]})
    sessao.commit()
    assert _post(cliente, job["job_id"], job["token"], {"eventos": _log()}).status_code == 401
    assert _auditorias(sessao, job["job_id"]) == ["instancia_revogada"]


def test_instancia_em_quarentena_termina_o_job_atual(cliente, sessao, job) -> None:
    sessao.execute(text("UPDATE direct_instances SET status = 'quarentena' WHERE id = :i"), {"i": job["instancia"]})
    sessao.commit()
    assert _post(cliente, job["job_id"], job["token"], {"eventos": _log()}).status_code == 200


def test_cenario_15_corpo_acima_do_limite_e_recusado_e_o_portal_continua(cliente, job) -> None:
    grande = b'{"eventos": [' + b'"x",' * 400_000 + b'"x"]}'
    assert len(grande) > 1_000_000
    assert _post(cliente, job["job_id"], job["token"], grande).status_code == 413
    assert _post(cliente, job["job_id"], job["token"], {"eventos": _log()}).status_code == 200
    print(f"\ncenário 15: corpo de {len(grande):,} bytes -> 413; o pedido seguinte foi aceito")


def test_cenario_15_evento_fora_do_schema_e_recusado_sem_perder_os_validos(cliente, sessao, job) -> None:
    eventos = Roteiro(DIA).emitir("execucao.iniciada").emitir("log", nivel="info", texto="ok").emitir(
        "log", nivel="info", texto="ok 2").eventos
    eventos[1]["payload"]["nivel"] = "verbose"
    eventos[2]["execution_id"] = "exe_de_outra_automacao"  # tentativa de apontar outro contexto
    resposta = _post(cliente, job["job_id"], job["token"], {"eventos": eventos})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ultima_sequencia"] == 3 and [r["sequence"] for r in corpo["recusados"]] == [2, 3]
    aceitos = sessao.execute(text("SELECT event_sequence FROM execution_events WHERE execution_attempt_id = :a"),
                             {"a": job["attempt_id"]}).scalars().all()
    assert aceitos == [1]
    print(f"\ncenário 15: lote com 2 eventos fora do contrato -> {len(corpo['recusados'])} recusados, 1 gravado")


def test_cenario_15_evento_acima_de_64kb_e_recusado(cliente, job) -> None:
    evento = Roteiro(DIA).emitir("log", nivel="info", texto="x").eventos[0]
    evento["payload"]["texto"] = "x" * 70_000
    resposta = _post(cliente, job["job_id"], job["token"], {"eventos": [evento]})
    assert resposta.status_code == 200 and resposta.json()["recusados"][0]["sequence"] == 1


@pytest.mark.parametrize("tipo,corpo,codigo", [
    ("text/plain", b"{}", 415),
    ("application/json", b"nao-e-json", 400),
    ("application/json", b'{"eventos": []}', 400),
])
def test_corpo_invalido_tem_resposta_clara(cliente, job, tipo, corpo, codigo) -> None:
    assert _post(cliente, job["job_id"], job["token"], corpo, tipo).status_code == codigo


def test_credencial_direta_nao_escreve_em_tentativa_do_agent(cliente, sessao, job) -> None:
    """A instância direta só alcança os próprios jobs, mesmo conhecendo o id de outra tentativa."""
    from modules.telemetry.application.dto import EventBatchCommand
    from modules.telemetry.application.use_cases import IngestExecutionEventBatch
    from modules.telemetry.domain.errors import ExecutionAttemptTelemetryError
    from modules.telemetry.infrastructure.adapters import build_telemetry_adapters

    ag = agente(sessao, maquina(sessao))
    _, job_agente = execucao(sessao, job["version_id"], DIA)
    tentativa = tentativa_agente(sessao, job_agente, ag)
    adapters = build_telemetry_adapters(sessao)
    evento = _log(0)[0]
    lote = [{"event_id": evento["event_id"], "event_sequence": 1, "event_type": "automation.event",
             "occurred_at": evento["occurred_at"], "payload": evento}]
    with pytest.raises(ExecutionAttemptTelemetryError):
        IngestExecutionEventBatch(adapters.attempts, adapters.events, adapters.acknowledgements, adapters.metrics,
                                  adapters.validator, adapters.masker, adapters.realtime, adapters.transaction,
                                  projector=adapters.projector).execute(EventBatchCommand(
            execution_attempt_id=tentativa, events=lote, agent_id=None, agent_instance_id=None,
            executor_type="direct", executor_id=job["instancia"]))


def test_comandos_do_job_sao_entregues_uma_vez(cliente, sessao, job) -> None:
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore

    SqlAlchemyDirectCommandStore(sessao).add(command_id="cmd_1", execution_attempt_id=job["attempt_id"], command={
        "protocol_version": "automation-events/1", "command_id": "cmd_1", "type": "parar_apos_item",
        "issued_at": "2026-11-09T14:00:00Z"})
    sessao.commit()
    cabecalho = {"Authorization": f"Bearer {job['token']}"}
    primeira = cliente.get(f"/api/v1/direto/jobs/{job['job_id']}/comandos", headers=cabecalho).json()
    segunda = cliente.get(f"/api/v1/direto/jobs/{job['job_id']}/comandos", headers=cabecalho).json()
    assert [c["type"] for c in primeira["comandos"]] == ["parar_apos_item"]
    assert segunda == {"comandos": []}
