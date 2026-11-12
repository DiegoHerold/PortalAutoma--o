"""Parar uma execução rodando (depois do item atual ou agora) e continuar a cancelada só com o
que não deu certo. Modo direto de verdade: fila, despacho, entrega do job, comandos e eventos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from modules.dispatch.api.fila import despachar_agora
from tests.db.semente import Roteiro, agente, maquina, tentativa_agente
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _conceder, _usuario
from tests.db.test_modo_direto_inscricao import Instancia, _codigo, admin  # noqa: F401 - fixture

ITENS = [{"chave": "5081", "rotulo": "Matriz"}, {"chave": "5076", "rotulo": "Filial A", "grupo": "5081"},
         {"chave": "5077", "rotulo": "Filial B", "grupo": "5081"}]


def _instancia_aprovada(cliente, sessao, admin) -> tuple[Instancia, dict[str, str], str]:
    instancia = Instancia(cliente)
    assert instancia.inscrever(_codigo(cliente, admin.automation_id)).status_code == 201
    mch = cliente.post("/api/v1/maquinas", json={"nome": f"PARAR-{uuid.uuid4().hex[:4]}"}).json()["id"]
    assert cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={"maquina_id": mch}).status_code == 200
    cab = {"Authorization": f"Bearer {instancia.sessao().json()['token']}"}
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa' AND id <> :m"), {"m": mch})
    sessao.commit()
    return instancia, cab, mch


def _situacao(cliente, execution_id: str):
    e = next(x for x in cliente.get("/api/v1/painel").json()["execucoes"] if x["execucao_id"] == execution_id)
    return e["situacao"]


def _status(sessao, tabela: str, id_: str) -> str:
    sessao.expire_all()
    return sessao.execute(text(f"SELECT status FROM {tabela} WHERE id = :i"), {"i": id_}).scalar_one()


def test_parar_depois_do_item_cancelar_agora_e_continuar_so_o_que_faltou(cliente, sessao, admin) -> None:
    _, cab, _ = _instancia_aprovada(cliente, sessao, admin)
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id, "itens": ITENS,
                                                         "parametros": {"competencia": "10/2026"}}).json()
    execution_id, job_id = pedido["execution_id"], pedido["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [job_id]
    job = cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"]
    cab_job = {"Authorization": f"Bearer {job['token']}"}
    eventos = f"/api/v1/direto/jobs/{job_id}/eventos"
    comandos = f"/api/v1/direto/jobs/{job_id}/comandos?espera=0"

    r = Roteiro(datetime.now(UTC))
    r.emitir("execucao.iniciada").emitir("item.iniciado", item="5081", rotulo="Matriz")
    r.emitir("etapa.iniciada", etapa="exportar", item="5081").emitir("etapa.concluida", etapa="exportar", item="5081", situacao="ok")
    r.emitir("item.concluido", item="5081", situacao="ok")
    r.emitir("item.iniciado", item="5076", rotulo="Filial A")
    r.emitir("etapa.iniciada", etapa="exportar", item="5076").emitir("etapa.concluida", etapa="exportar", item="5076", situacao="ok")
    r.emitir("etapa.iniciada", etapa="integrar", item="5076")
    assert cliente.post(eventos, json={"eventos": r.eventos}, headers=cab_job).status_code == 200
    assert _situacao(cliente, execution_id) is None  # rodando normal: nenhuma linha extra no cartão

    # 1) Parar depois do item atual: vira comando para a automação, que o busca sozinha.
    parar = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "apos_item"})
    assert parar.status_code == 200, parar.text
    assert parar.json()["avisadas"] == 1 and _status(sessao, "task_executions", job_id) == "running"
    assert _situacao(cliente, execution_id)["tipo"] == "parando"
    recebidos = cliente.get(comandos, headers=cab_job).json()["comandos"]
    assert [c["type"] for c in recebidos] == ["parar_apos_item"]
    assert _situacao(cliente, execution_id)["recebido"] is True

    # 2) Mudou de ideia: cancelar agora. O job fica "cancelando" até a automação parar.
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "agora"}).status_code == 200
    assert _status(sessao, "task_executions", job_id) == "cancelling"
    assert _situacao(cliente, execution_id)["tipo"] == "cancelando"
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "agora"}).status_code == 200
    assert [c["type"] for c in cliente.get(comandos, headers=cab_job).json()["comandos"]] == ["cancelar"]  # sem repetir
    previa = cliente.get(f"/api/v1/fila/execucoes/{execution_id}/continuar").json()
    assert previa["pode"] is False and "não terminou" in previa["motivo"]

    # 3) A automação obedece e declara o fim.
    ja = len(r.eventos)
    r.emitir("etapa.concluida", etapa="integrar", item="5076", situacao="interrompida")
    r.emitir("item.concluido", item="5076", situacao="cancelado").emitir("execucao.concluida", situacao="interrompida")
    assert cliente.post(eventos, json={"eventos": r.eventos[ja:]}, headers=cab_job).status_code == 200
    assert _status(sessao, "task_executions", job_id) == "cancelled"
    assert _status(sessao, "orchestration_executions", execution_id) == "cancelled"  # parada por pessoa não é falha
    assert execution_id not in [x["execucao_id"] for x in cliente.get("/api/v1/painel").json()["execucoes"]]

    # 4) Continuar: só o que não deu certo (5076 interrompido e 5077 que nem começou); 5081 é pulado.
    previa = cliente.get(f"/api/v1/fila/execucoes/{execution_id}/continuar").json()
    assert previa["pode"] is True and previa["pular"] == 1
    assert [(i["chave"], i["situacao"]) for i in previa["refazer"]] == [("5076", "cancelado"), ("5077", "pendente")]

    pessoa, _ = _usuario(sessao, "viewer")
    _conceder(sessao, admin.automation_id, pessoa, ["ver_execucoes"])
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(f"/api/v1/fila/execucoes/{execution_id}/continuar").status_code == 200
        assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/continuar").status_code == 403
        assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "agora"}).status_code == 403

    continuar = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/continuar")
    assert continuar.status_code == 201, continuar.text
    nova = continuar.json()
    assert nova["itens"] == 2 and nova["pulados"] == 1 and nova["execution_id"] != execution_id
    segunda = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/continuar")
    assert segunda.status_code == 409 and "já foi continuada" in segunda.text, segunda.text
    sessao.expire_all()
    entrada = sessao.execute(text("SELECT input FROM orchestration_executions WHERE id = :i"), {"i": nova["execution_id"]}).scalar_one()
    assert entrada["continua_de"] == execution_id
    acompanhar = cliente.get(f"/api/v1/execucoes/{execution_id}/acompanhar").json()
    assert acompanhar["execucao"]["continuada_em"] == nova["execution_id"]

    # 5) A automação recebe só os dois itens, cada um com o que já tinha sido feito.
    novo_job = nova["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [novo_job]
    entregue = cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"]
    itens = {i["chave"]: i for i in entregue["itens"]}
    assert sorted(itens) == ["5076", "5077"]
    assert itens["5076"]["retomada"] == {"execucao_anterior": execution_id, "situacao_anterior": "cancelado",
                                         "etapas_concluidas": ["exportar"]}
    assert itens["5077"]["retomada"]["etapas_concluidas"] == []
    assert entregue["parametros"] == {"competencia": "10/2026"} and itens["5076"]["grupo"] == "5081"

    acoes = [a for (a,) in sessao.execute(text(
        "SELECT action FROM audit_events WHERE resource_id = :e AND action LIKE 'execucao.%' ORDER BY occurred_at"),
        {"e": execution_id})]
    assert acoes == ["execucao.parada_pedida"] * 3 + ["execucao.continuada"]  # cada clique fica registrado
    print("\nparar: apos_item -> comando entregue; agora -> cancelando; automação interrompe -> cancelada; "
          "continuar -> nova execução só com 5076 (pula a etapa exportar) e 5077")


def test_parar_job_que_ainda_esta_na_fila_cancela_na_hora(cliente, sessao, admin) -> None:
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa'"))
    sessao.commit()
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": "9001"}, {"chave": "9002"}]}).json()
    execution_id = pedido["execution_id"]
    resposta = cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "apos_item"})
    assert resposta.status_code == 200 and resposta.json()["canceladas_na_fila"] == 2
    assert _status(sessao, "orchestration_executions", execution_id) == "cancelled"
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "agora"}).status_code == 409
    previa = cliente.get(f"/api/v1/fila/execucoes/{execution_id}/continuar").json()
    assert previa["pode"] is True and len(previa["refazer"]) == 2
    assert cliente.post(f"/api/v1/fila/execucoes/{execution_id}/parar", json={"modo": "outro"}).status_code == 409
    assert cliente.post("/api/v1/fila/execucoes/exe_inexistente/parar", json={"modo": "agora"}).status_code == 404


def test_cancelar_pela_fila_fecha_a_execucao(cliente, sessao, admin) -> None:
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa'"))
    sessao.commit()
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": "9101"}]}).json()
    assert cliente.post(f"/api/v1/fila/jobs/{pedido['jobs'][0]['job_id']}/cancelar").status_code == 200
    assert _status(sessao, "orchestration_executions", pedido["execution_id"]) == "cancelled"


def test_modo_agente_so_cancela_agora(cliente, sessao, admin) -> None:
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa'"))
    sessao.commit()
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": "9201"}]}).json()
    job_id = pedido["jobs"][0]["job_id"]
    ag = agente(sessao, maquina(sessao))
    tentativa_agente(sessao, job_id, ag)
    sessao.execute(text("UPDATE task_executions SET status = 'running', current_attempt_number = 1 WHERE id = :j"), {"j": job_id})
    sessao.commit()
    resposta = cliente.post(f"/api/v1/fila/execucoes/{pedido['execution_id']}/parar", json={"modo": "apos_item"})
    assert resposta.status_code == 409 and "modo agente" in resposta.text, resposta.text
    assert _status(sessao, "task_executions", job_id) == "running"  # nada mudou
