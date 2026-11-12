"""Comunicação com a automação no modo direto (12/11/2026).

- 30 s sem sinal da instância: o Painel mostra "comunicação não está ativa" e vira notificação;
- 2 min sem sinal: a execução é cancelada com erro, a máquina é liberada e o token revogado;
- cancelamento sem resposta em 2 min: o Painel mostra o erro e "Encerrar no Portal" funciona.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from modules.dispatch.api.fila import despachar_agora
from tests.db.semente import Roteiro
from tests.db.test_modo_direto_inscricao import admin  # noqa: F401 - fixture
from tests.db.test_parar_e_continuar import _instancia_aprovada, _situacao, _status


def _rodando(cliente, sessao, admin, chave: str):
    instancia, cab, mch = _instancia_aprovada(cliente, sessao, admin)
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": chave, "rotulo": f"Empresa {chave}"}]}).json()
    execution_id, job_id = pedido["execution_id"], pedido["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [job_id]
    job = cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"]
    cab_job = {"Authorization": f"Bearer {job['token']}"}
    eventos = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").emitir("item.iniciado", item=chave).eventos
    assert cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": eventos}, headers=cab_job).status_code == 200
    tentativa = sessao.execute(text("SELECT id FROM execution_attempts WHERE task_execution_id = :t"), {"t": job_id}).scalar_one()
    return instancia, mch, execution_id, job_id, tentativa, cab_job


def _sem_sinal_ha(sessao, instancia, tentativa: str, segundos: int) -> None:
    sessao.execute(text("UPDATE direct_instances SET last_seen_at = now() - make_interval(secs => :s) WHERE id = :i"),
                   {"s": segundos, "i": instancia.id})
    sessao.execute(text("UPDATE execution_attempts SET created_at = now() - interval '10 minutes' WHERE id = :a"), {"a": tentativa})
    sessao.commit()


def test_sem_comunicacao_avisa_e_em_2_min_cancela_com_erro(cliente, sessao, admin) -> None:
    from modules.telemetry.infrastructure.repositories.sqlalchemy_notificacoes import SqlAlchemyLeituraDeOcorrencias

    instancia, mch, execution_id, job_id, tentativa, cab_job = _rodando(cliente, sessao, admin, "7001")
    # O primeiro job começou: a execução sai de "queued".
    assert _status(sessao, "orchestration_executions", execution_id) == "running"
    assert _situacao(cliente, execution_id) is None

    _sem_sinal_ha(sessao, instancia, tentativa, 45)
    situacao = _situacao(cliente, execution_id)
    assert situacao["tipo"] == "sem_comunicacao" and situacao["cancela_em"]
    avisos = [c for c in SqlAlchemyLeituraDeOcorrencias(sessao).comunicacao(datetime.now(UTC)) if c["attempt_id"] == tentativa]
    assert [c["tipo"] for c in avisos] == ["sem_comunicacao"]
    assert despachar_agora(sessao)["perdidos"] == 0  # 45 s: ainda espera
    assert _status(sessao, "task_executions", job_id) == "running"

    _sem_sinal_ha(sessao, instancia, tentativa, 150)
    assert despachar_agora(sessao)["perdidos"] == 1
    assert _status(sessao, "task_executions", job_id) == "cancelled"
    assert _status(sessao, "orchestration_executions", execution_id) == "cancelled"
    falha = sessao.execute(text("SELECT failure_summary FROM task_executions WHERE id = :t"), {"t": job_id}).scalar_one()
    assert falha.startswith("Sem comunicação com a automação por 2 min")
    travas = sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                            {"m": mch}).scalar_one()
    assert travas == 0  # máquina liberada
    # A automação, se voltar, é recusada (o SDK 0.4.0 entende 401 como "o Portal encerrou").
    volta = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").emitir("log", nivel="info", texto="voltei").eventos[1:]
    volta[0]["sequence"] = 3
    assert cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": volta}, headers=cab_job).status_code == 401
    print("\ncomunicação: 45 s -> aviso 'comunicação não está ativa'; 2 min -> cancelada com erro, máquina livre, token revogado")


def test_cancelamento_sem_resposta_mostra_erro_e_encerra_no_portal(cliente, sessao, admin) -> None:
    from modules.telemetry.infrastructure.repositories.sqlalchemy_notificacoes import SqlAlchemyLeituraDeOcorrencias

    _instancia, mch, execution_id, job_id, tentativa, cab_job = _rodando(cliente, sessao, admin, "7101")
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "agora"}).status_code == 200
    cedo = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/encerrar")
    assert cedo.status_code == 409 and "2 min" in cedo.text
    assert _situacao(cliente, execution_id)["tipo"] == "cancelando"

    # A automação recebe o comando, mas não para (SDK antigo, ou presa fora do Python).
    assert cliente.get(f"/api/v1/direto/jobs/{job_id}/comandos?espera=0", headers=cab_job).json()["comandos"]
    sessao.execute(text("UPDATE direct_commands SET created_at = now() - interval '3 minutes' WHERE execution_attempt_id = :a"),
                   {"a": tentativa})
    sessao.commit()
    situacao = _situacao(cliente, execution_id)
    assert situacao == {**situacao, "tipo": "cancelamento_sem_resposta", "recebido": True}
    avisos = [c for c in SqlAlchemyLeituraDeOcorrencias(sessao).comunicacao(datetime.now(UTC)) if c["attempt_id"] == tentativa]
    assert [(c["tipo"], c["recebido"]) for c in avisos] == [("cancelamento_sem_resposta", True)]

    encerrar = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/encerrar")
    assert encerrar.status_code == 200 and encerrar.json()["encerradas"] == 1
    assert _status(sessao, "task_executions", job_id) == "cancelled"
    assert _status(sessao, "orchestration_executions", execution_id) == "cancelled"
    falha = sessao.execute(text("SELECT failure_summary FROM task_executions WHERE id = :t"), {"t": job_id}).scalar_one()
    assert falha == "Encerrada no Portal: a automação recebeu o cancelamento e não parou em 2 min."
    assert sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                          {"m": mch}).scalar_one() == 0
    assert cliente.get(f"/api/v1/direto/jobs/{job_id}/comandos?espera=0", headers=cab_job).status_code == 401
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/encerrar").status_code == 409  # já terminou
    acoes = [a for (a,) in sessao.execute(text("SELECT action FROM audit_events WHERE resource_id = :e ORDER BY occurred_at"),
                                          {"e": execution_id})]
    assert "execucao.encerrada_no_portal" in acoes
    # Continuar continua valendo depois de encerrar no Portal.
    assert cliente.get(f"/api/v1/fila/execucoes/{execution_id}/continuar").json()["pode"] is True
    print("\ncancelamento sem resposta: 2 min -> erro no Painel; Encerrar no Portal cancela, libera a máquina e revoga o token")


def test_ocorrencias_de_comunicacao_viram_erro() -> None:
    from modules.telemetry.domain.notificacoes import ERRO, cancelamento_sem_resposta, sem_comunicacao

    agora = datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
    a = sem_comunicacao("exe_1", "att_1", 7, "Folha", agora - timedelta(seconds=40))
    b = cancelamento_sem_resposta("exe_1", "att_1", 7, "Folha", False, agora)
    assert a.tipos == b.tipos == frozenset({ERRO})
    assert a.titulo == "Folha: comunicação não está ativa" and a.chave == "sem_comunicacao:att_1"
    assert "não recebeu o cancelamento" in b.texto and b.link == "/execucoes/exe_1"
