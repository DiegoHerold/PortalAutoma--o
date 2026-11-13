"""Pendências com "Continuar processo" (13/11/2026) no PostgreSQL e pela API real.

Item em atenção vira pendência; o e-mail da automação ganha o botão; continuar põe na Fila uma
execução só com o item; o segundo clique (ou outro caminho) diz quem já continuou; sem e-mail da
automação, o Portal avisa quem pediu; rodar o item de novo fecha a pendência."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.db.semente import Roteiro
from tests.db.test_comunicacao import _rodando
from tests.db.test_correio import Carteiro
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _usuario
from tests.db.test_modo_direto_inscricao import admin  # noqa: F401 - fixture


def _atencao(cliente, job_id: str, cab_job: dict, item: str, concluir: bool = True) -> None:
    roteiro = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").emitir("item.iniciado", item=item)
    roteiro.emitir("atencao", item=item, motivo="2 rubricas a parametrizar")
    roteiro.emitir("item.concluido", item=item, situacao="atencao")
    if concluir:
        roteiro.emitir("execucao.concluida", situacao="atencao")
    r = cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": roteiro.eventos[2:]}, headers=cab_job)
    assert r.status_code == 200 and r.json()["recusados"] == [], r.text


def test_email_da_automacao_com_botao_e_continuar_uma_vez(cliente, sessao, admin, monkeypatch) -> None:
    import modules.telemetry.infrastructure.email_graph as graph

    carteiro = Carteiro()
    monkeypatch.setattr(graph, "montar_carteiro", lambda settings: carteiro)
    _, _, execution_id, job_id, _, cab_job = _rodando(cliente, sessao, admin, "9301")
    _atencao(cliente, job_id, cab_job, "9301", concluir=False)
    cliente.post("/api/v1/emails/dominios", json={"dominio": "cliente-pend.com.br"})
    email = cliente.post(f"/api/v1/direto/jobs/{job_id}/emails", headers=cab_job, json={
        "para": ["analista@cliente-pend.com.br"], "assunto": "Folha 10/2026: rubricas a parametrizar",
        "html": "<p>Parametrize:</p>{{continuar}}<p>Obrigado</p>", "continuar": ["9301"]})
    assert email.status_code == 201, email.text
    corpo = carteiro.enviados[0]["html"]
    link = re.search(r"href='([^']+/pendencias/(pav_[0-9a-f]+))'", corpo)
    assert link and corpo.index("Parametrize") < corpo.index("Continuar processo") < corpo.index("Obrigado")
    aviso = link.group(2)
    _atencao(cliente, job_id, cab_job, "9301")  # os mesmos eventos de novo (idempotentes) e o fim da execução

    lista = cliente.get("/api/v1/pendencias").json()["execucoes"]
    grupo = next(g for g in lista if g["execucao_id"] == execution_id)
    assert [(i["item"], i["situacao"], i["motivo"]) for i in grupo["itens"]] == [("9301", "aguardando", "2 rubricas a parametrizar")]
    visto = cliente.get(f"/api/v1/pendencias/avisos/{aviso}").json()
    assert visto["aguardando"] == 1 and visto["pode_continuar"] is True and visto["resolucao"] is None

    # Quem não pode executar não continua; quem não vê a automação nem vê a pendência.
    pessoa, _ = _usuario(sessao, "sem_permissao")
    with como(cliente, pessoa, "sem_permissao"):
        assert cliente.get(f"/api/v1/pendencias/avisos/{aviso}").status_code == 404
        assert cliente.post(f"/api/v1/pendencias/avisos/{aviso}/continuar").status_code == 403

    continuado = cliente.post(f"/api/v1/pendencias/avisos/{aviso}/continuar")
    assert continuado.status_code == 200, continuado.text
    nova = continuado.json()["execucao_id"]
    assert continuado.json()["itens"] == ["9301"] and nova != execution_id
    linha = sessao.execute(text("SELECT origin, requested_by, input FROM orchestration_executions WHERE id = :e"), {"e": nova}).one()
    assert linha.origin == "pendencia" and linha.requested_by == "1" and linha.input["itens"] == ["9301"]
    rotulo = sessao.execute(text("SELECT input FROM task_executions WHERE execution_id = :e"), {"e": nova}).scalar_one()
    assert rotulo["dados_dos_itens"][0]["rotulo"] == "Empresa 9301"  # o retrato do pedido original

    # O botão vale uma vez: de novo (pelo e-mail ou pelo Portal), diz quem já continuou.
    for url in (f"/api/v1/pendencias/avisos/{aviso}/continuar", f"/api/v1/pendencias/execucoes/{execution_id}/continuar"):
        de_novo = cliente.post(url)
        assert de_novo.status_code == 409, de_novo.text
        assert de_novo.json()["resolucao"]["resolvida_via"] == "email"
        assert de_novo.json()["resolucao"]["continuacao_execucao_id"] == nova
    assert cliente.get(f"/api/v1/pendencias/avisos/{aviso}").json()["pode_continuar"] is False
    auditoria = sessao.execute(text("SELECT after FROM audit_events WHERE action = 'pendencia.continuada' AND resource_id = :e"),
                               {"e": execution_id}).scalar_one()
    assert auditoria["via"] == "email" and auditoria["nova_execucao"] == nova
    print("\npendências: e-mail da automação com o botão no lugar marcado; continuar uma vez; segunda vez 409 com quem e "
          "quando; sem permissão 403")


def test_sem_email_da_automacao_o_portal_avisa_quem_pediu_e_outra_execucao_fecha(cliente, sessao, admin, monkeypatch) -> None:
    import modules.telemetry.infrastructure.email_graph as graph
    from modules.orchestration.pendencias.api import pendencias

    carteiro = Carteiro()
    monkeypatch.setattr(graph, "montar_carteiro", lambda settings: carteiro)
    sessao.execute(text("UPDATE users SET email = 'gestor-pend@biason.net', is_active = true WHERE id = 1"))
    sessao.commit()
    _, _, execution_id, job_id, _, cab_job = _rodando(cliente, sessao, admin, "9302")
    _atencao(cliente, job_id, cab_job, "9302")

    servico = pendencias(sessao)
    assert servico.avisar_por_padrao()["avisados"] == 0  # espera um pouco: a automação ainda pode mandar o dela
    sessao.commit()
    servico._agora = lambda: datetime.now(UTC) + timedelta(minutes=2)
    assert servico.avisar_por_padrao()["avisados"] == 1
    sessao.commit()
    enviado = next(e for e in carteiro.enviados if "aguardando você" in e["assunto"])
    assert enviado["para"] == ["gestor-pend@biason.net"] and "Continuar processo" in enviado["html"]
    assert "2 rubricas a parametrizar" in enviado["html"]
    assert servico.avisar_por_padrao()["avisados"] == 0  # um aviso só
    sessao.commit()

    # O item rodou de novo pelo Executar: a pendência fecha e o botão não continua mais.
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": "9302", "rotulo": "Empresa 9302"}]})
    assert pedido.status_code == 201
    situacao = cliente.get(f"/api/v1/pendencias/execucoes/{execution_id}").json()
    assert situacao["aguardando"] == 0 and situacao["resolucao"]["situacao"] == "substituida"
    assert situacao["resolucao"]["resolvida_via"] == "outra_execucao"
    assert cliente.post(f"/api/v1/pendencias/execucoes/{execution_id}/continuar").status_code == 409
    print("\npendências: sem e-mail da automação, o Portal avisa quem pediu (uma vez); rodar o item de novo fecha a pendência")
