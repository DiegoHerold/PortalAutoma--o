"""Cenários da Fase 2 de ponta a ponta no PostgreSQL: evento -> ingestão real -> projeção ->
histórico -> estimativa na API. Cada cenário imprime o que verificou (pytest -s)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.db.semente import (
    Roteiro,
    agente,
    automacao,
    empresa,
    enviar_pelo_agente,
    execucao,
    instancia_direta,
    maquina,
    tentativa_agente,
    tentativa_direta,
)

DIA1 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _estimativa(cliente, execution_id: str) -> dict:
    resposta = cliente.get(f"/api/v1/executions/{execution_id}/estimativa")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _etapa(estimativa: dict, etapa: str, item: str | None) -> dict:
    return next(l for l in estimativa["jobs"][0]["etapas"] if l["etapa"] == etapa and l["item"] == item)


def _historico_pelo_agente(sessao, version_id: int, ag, dia: datetime, codigo: str, **opcoes) -> str:
    execution_id, job_id = execucao(sessao, version_id, dia)
    attempt_id = tentativa_agente(sessao, job_id, ag)
    r = Roteiro(dia + timedelta(minutes=1)).emitir("execucao.iniciada").etapa("iniciar", 30)
    empresa(r, codigo, **opcoes)
    r.etapa("aviso", 5).emitir("execucao.concluida", situacao="ok")
    enviar_pelo_agente(sessao, attempt_id, ag, r.eventos)
    return execution_id


def _iniciar(sessao, version_id: int, ag, quando: datetime, codigos: list[str], separa: bool = True) -> tuple[str, str, str]:
    """Execução que começa agora: só o início e os itens, para ver a estimativa congelada."""
    execution_id, job_id = execucao(sessao, version_id, quando)
    attempt_id = tentativa_agente(sessao, job_id, ag)
    r = Roteiro(quando + timedelta(seconds=5)).emitir("execucao.iniciada")
    for codigo in codigos:
        r.emitir("item.iniciado", item=codigo, rotulo=codigo, grupo=codigo, configuracao={"separar_por_custo": separa})
    enviar_pelo_agente(sessao, attempt_id, ag, r.eventos)
    return execution_id, job_id, attempt_id


def test_cenario_6_item_novo_mostra_sem_historico_sem_usar_outro_item(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    for dia in range(3):
        _historico_pelo_agente(sessao, version_id, ag, DIA1 + timedelta(days=dia), "5066", separa=True, centros=50,
                               seg_troca=20, seg_por_centro=10)

    execution_id, _, _ = _iniciar(sessao, version_id, ag, DIA1 + timedelta(days=10), ["5066", "9999"])
    est = _estimativa(cliente, execution_id)

    conhecido = _etapa(est, "rubricas", "5066")
    novo = _etapa(est, "rubricas", "9999")
    assert conhecido["estimativa_s"] == 500 and conhecido["base"]["texto"] == "últimas 3 execuções do item"
    assert novo["estimativa_s"] is None and novo["base"] is None
    assert novo["motivo_texto"] == "rodando pela primeira vez, sem histórico de estimativas"
    assert est["estimativa"]["completa"] is False and est["estimativa"]["sem_base"] == 3  # trocar, rubricas, txt do 9999
    print(f"\ncenário 6: 5066 rubricas ~{conhecido['estimativa_s']:.0f}s ({conhecido['base']['texto']}); "
          f"9999 rubricas: {novo['motivo_texto']}; job: pelo menos {est['estimativa']['segundos']:.0f}s, "
          f"{est['estimativa']['sem_base']} etapa(s) sem base")


def test_cenario_7_parada_em_atencao_so_as_etapas_que_rodaram_entram_no_historico(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    _historico_pelo_agente(sessao, version_id, ag, DIA1, "5081", separa=False, centros=1, seg_troca=15,
                           seg_por_centro=60, atencao=True)

    rodadas = sessao.execute(text("SELECT step_key, status FROM step_runs WHERE automation_id = :a ORDER BY started_at"),
                             {"a": automation_id}).all()
    assert [r.step_key for r in rodadas] == ["iniciar", "trocar_empresa", "rubricas", "aviso"]
    item = sessao.execute(text("SELECT status, attention FROM execution_items WHERE automation_id = :a"),
                          {"a": automation_id}).one()
    assert item.status == "atencao" and item.attention["motivo"] == "Rubricas a parametrizar"

    execution_id, _, _ = _iniciar(sessao, version_id, ag, DIA1 + timedelta(days=1), ["5081"], separa=False)
    est = _estimativa(cliente, execution_id)
    assert _etapa(est, "rubricas", "5081")["estimativa_s"] is not None
    assert _etapa(est, "txt", "5081")["estimativa_s"] is None
    print(f"\ncenário 7: etapas no histórico {[r.step_key for r in rodadas]}; txt sem base, rubricas com base")


def test_cenario_8_retomada_estima_so_o_que_falta(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    _historico_pelo_agente(sessao, version_id, ag, DIA1, "5066", separa=True, centros=50, seg_troca=20, seg_por_centro=10)

    execution_id, job_id = execucao(sessao, version_id, DIA1 + timedelta(days=5))
    primeira = tentativa_agente(sessao, job_id, ag, 1)
    r = Roteiro(DIA1 + timedelta(days=5, minutes=1)).emitir("execucao.iniciada")
    r.emitir("item.iniciado", item="5066", grupo="5066", configuracao={"separar_por_custo": True})
    r.etapa("rubricas", 300, item="5066", tarefas=30, previstas=50, situacao="erro")
    enviar_pelo_agente(sessao, primeira, ag, r.eventos)

    segunda = tentativa_agente(sessao, job_id, ag, 2)
    r2 = Roteiro(DIA1 + timedelta(days=5, hours=1)).emitir("execucao.iniciada")
    r2.emitir("item.iniciado", item="5066", grupo="5066", configuracao={"separar_por_custo": True})
    enviar_pelo_agente(sessao, segunda, ag, r2.eventos)

    linha = _etapa(_estimativa(cliente, execution_id), "rubricas", "5066")
    assert linha["segundos_por_tarefa"] == 10
    assert linha["tarefas_restantes"] == 20
    assert linha["estimativa_s"] == 200
    print(f"\ncenário 8: 30 de 50 centros feitos na 1ª tentativa; retomada estima "
          f"{linha['tarefas_restantes']} x {linha['segundos_por_tarefa']:.0f}s = {linha['estimativa_s']:.0f}s")


def test_cenario_17_mesmo_historico_e_mesma_estimativa_nos_dois_modos(sessao, cliente) -> None:
    resultados = {}
    for modo in ("agente", "direto"):
        automation_id, version_id = automacao(sessao)
        mch = maquina(sessao)
        if modo == "agente":
            ag = agente(sessao, mch)
        else:
            instancia = instancia_direta(sessao, automation_id, mch)
        for dia in range(2):
            execution_id, job_id = execucao(sessao, version_id, DIA1 + timedelta(days=dia))
            r = Roteiro(DIA1 + timedelta(days=dia, minutes=1)).emitir("execucao.iniciada").etapa("iniciar", 30)
            with_pausa = r.emitir("pausa.iniciada", motivo="reinicio").passar(60).emitir("pausa.concluida", motivo="reinicio")
            empresa(with_pausa, "5066", separa=True, centros=10 + dia * 10, seg_troca=20, seg_por_centro=12)
            r.etapa("aviso", 5).emitir("execucao.concluida", situacao="ok")
            if modo == "agente":
                enviar_pelo_agente(sessao, tentativa_agente(sessao, job_id, ag), ag, r.eventos)
            else:
                _, token = tentativa_direta(sessao, job_id, instancia, mch)
                resposta = cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": r.eventos},
                                        headers={"Authorization": f"Bearer {token}"})
                assert resposta.status_code == 200 and resposta.json()["recusados"] == [], resposta.text
        historico = sessao.execute(text(
            "SELECT step_key, item_key, status, tasks, net_seconds, paused_seconds, executor_type FROM step_runs"
            " WHERE automation_id = :a ORDER BY completed_at, step_key"), {"a": automation_id}).all()
        if modo == "agente":
            execution_id, _, _ = _iniciar(sessao, version_id, ag, DIA1 + timedelta(days=9), ["5066"])
        else:
            execution_id, job_id = execucao(sessao, version_id, DIA1 + timedelta(days=9))
            _, token = tentativa_direta(sessao, job_id, instancia, mch)
            r = Roteiro(DIA1 + timedelta(days=9, seconds=5)).emitir("execucao.iniciada")
            r.emitir("item.iniciado", item="5066", grupo="5066", configuracao={"separar_por_custo": True})
            assert cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": r.eventos},
                                headers={"Authorization": f"Bearer {token}"}).status_code == 200
        est = _estimativa(cliente, execution_id)
        resultados[modo] = (historico, [(l["etapa"], l["item"], l["estimativa_s"], l["base"]) for l in est["jobs"][0]["etapas"]],
                            est["estimativa"])

    def sem_executor(linhas):
        return [tuple(l[:-1]) for l in linhas]

    assert sem_executor(resultados["agente"][0]) == sem_executor(resultados["direto"][0])
    assert {l.executor_type for l in resultados["agente"][0]} == {"agent"}
    assert {l.executor_type for l in resultados["direto"][0]} == {"direct"}
    assert resultados["agente"][1] == resultados["direto"][1]
    assert resultados["agente"][2] == resultados["direto"][2]
    iniciar = next(l for l in resultados["agente"][0] if l.step_key == "iniciar")
    assert iniciar.net_seconds == 30 and iniciar.paused_seconds == 0  # a pausa foi fora da etapa iniciar
    print(f"\ncenário 17: {len(resultados['agente'][0])} etapas medidas idênticas nos dois modos; "
          f"estimativa do job {resultados['agente'][2]['segundos']:.0f}s igual nos dois")


def test_regra_7_no_banco_pausa_dentro_da_etapa_sai_da_duracao(sessao) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    execution_id, job_id = execucao(sessao, version_id, DIA1)
    r = Roteiro(DIA1).emitir("execucao.iniciada")
    r.emitir("item.iniciado", item="5066", configuracao={"separar_por_custo": True})
    r.emitir("etapa.iniciada", etapa="rubricas", item="5066", tarefas_previstas=10).passar(100)
    r.emitir("pausa.iniciada", motivo="reinicio", detalhe="Domínio lenta").passar(65)
    r.emitir("pausa.concluida", motivo="reinicio").passar(35)
    r.emitir("etapa.concluida", etapa="rubricas", item="5066", situacao="ok", tarefas=10)
    enviar_pelo_agente(sessao, tentativa_agente(sessao, job_id, ag), ag, r.eventos)

    linha = sessao.execute(text("SELECT gross_seconds, paused_seconds, net_seconds FROM step_runs WHERE execution_id = :e"),
                           {"e": execution_id}).one()
    assert (linha.gross_seconds, linha.paused_seconds, linha.net_seconds) == (200, 65, 135)
    print(f"\nregra 7: etapa de {linha.gross_seconds:.0f}s com {linha.paused_seconds:.0f}s de reinício -> "
          f"{linha.net_seconds:.0f}s na base")


def test_regra_8_estimativa_congelada_nao_muda_depois(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    _historico_pelo_agente(sessao, version_id, ag, DIA1, "5066", separa=True, centros=10, seg_troca=20, seg_por_centro=10)
    execution_id, _, _ = _iniciar(sessao, version_id, ag, DIA1 + timedelta(days=2), ["5066"])
    antes = _estimativa(cliente, execution_id)

    for dia in (3, 4, 5):  # execuções que terminam depois: não podem mudar a estimativa mostrada
        _historico_pelo_agente(sessao, version_id, ag, DIA1 + timedelta(days=dia), "5066", separa=True, centros=10,
                               seg_troca=999, seg_por_centro=99)
    depois = _estimativa(cliente, execution_id)
    assert antes == depois
    print(f"\nregra 8: estimativa {antes['estimativa']['segundos']:.0f}s igual antes e depois de 3 execuções novas")


def test_regra_6_no_banco_mudar_separar_por_custo_zera_a_base(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    _historico_pelo_agente(sessao, version_id, ag, DIA1, "5066", separa=False, centros=1, seg_troca=20, seg_por_centro=80)
    execution_id, _, _ = _iniciar(sessao, version_id, ag, DIA1 + timedelta(days=1), ["5066"])  # agora separa por custo
    linha = _etapa(_estimativa(cliente, execution_id), "rubricas", "5066")
    assert linha["estimativa_s"] is None and linha["motivo"] == "configuracao_mudou"
    print(f"\nregra 6: {linha['motivo_texto']}")


def test_tempos_por_etapa_de_um_item_nunca_misturam_itens(sessao, cliente) -> None:
    automation_id, version_id = automacao(sessao)
    ag = agente(sessao, maquina(sessao))
    _historico_pelo_agente(sessao, version_id, ag, DIA1, "5066", separa=True, centros=10, seg_troca=20, seg_por_centro=10)
    _historico_pelo_agente(sessao, version_id, ag, DIA1 + timedelta(days=1), "5081", separa=True, centros=10,
                           seg_troca=200, seg_por_centro=100)
    resposta = cliente.get(f"/api/v1/automations/{automation_id}/tempos", params={"item": "5066"})
    assert resposta.status_code == 200, resposta.text
    por_etapa = {e["etapa"]: e for e in resposta.json()["etapas"]}
    assert por_etapa["trocar_empresa"]["tipico_s"] == 20 and por_etapa["trocar_empresa"]["execucoes"] == 1
    assert por_etapa["rubricas"]["por_tarefa_s"] == 10
    assert por_etapa["iniciar"]["base"] == "automacao" and por_etapa["iniciar"]["execucoes"] == 2
    print(f"\ntempos do 5066: trocar {por_etapa['trocar_empresa']['tipico_s']:.0f}s, rubricas "
          f"{por_etapa['rubricas']['por_tarefa_s']:.0f}s/tarefa (o 5081 levou 10x mais e não entrou)")
