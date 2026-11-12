"""Cenários da Fase 3 no PostgreSQL: fila, despacho, trava de tela por máquina e job perdido."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from modules.dispatch.api.fila import despachar_agora
from modules.dispatch.infrastructure.adapters.fila import build_fila
from modules.dispatch.infrastructure.repositories.sqlalchemy_queue_view import SqlAlchemyQueueReader
from tests.db.semente import (
    Roteiro,
    agente,
    automacao,
    empresa,
    enviar_pelo_agente,
    execucao,
    instancia_com_sinal,
    instancia_direta,
    maquina,
    publicar,
    tentativa_agente,
)

import pytest

AGORA = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _so_as_maquinas_do_cenario(sessao):
    """Cada cenário começa sem as máquinas dos testes anteriores (o banco de teste é da sessão)."""
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa'"))
    sessao.execute(text("UPDATE task_executions SET status = 'cancelled' WHERE status IN ('queued', 'ready')"
                        " AND enqueue_batch_id IS NOT NULL"))
    sessao.commit()
DIA1 = AGORA - timedelta(days=30)


def _automacao_publicada(sessao) -> tuple[int, int]:
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    return automation_id, version_id


def _pedir(cliente, version_id: int, itens: list[dict], prioridade: int = 0, parametros: dict | None = None) -> dict:
    resposta = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": version_id, "itens": itens,
                                                           "parametros": parametros or {"competencia": "10/2026"},
                                                           "prioridade": prioridade})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _item(chave: str, grupo: str | None = None, separa: bool = True) -> dict:
    return {"chave": chave, "rotulo": f"Empresa {chave}", "grupo": grupo or chave, "configuracao": {"separar_por_custo": separa}}


def _fila(cliente) -> dict:
    resposta = cliente.get("/api/v1/fila")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _maquina_direta(sessao, automation_id: int, nome: str) -> tuple[str, str]:
    mch = maquina(sessao, nome)
    instancia = instancia_direta(sessao, automation_id, mch)
    instancia_com_sinal(sessao, instancia)
    return mch, instancia


def test_cenario_4_pedido_repetido_aponta_para_o_job_existente(sessao, cliente) -> None:
    _, version_id = _automacao_publicada(sessao)
    primeiro = _pedir(cliente, version_id, [_item("5066")])
    segundo = _pedir(cliente, version_id, [_item("5066")])
    assert primeiro["jobs"][0]["existente"] is False and primeiro["execution_id"] is not None
    assert segundo["jobs"] == [{"job_id": primeiro["jobs"][0]["job_id"], "itens": ["5066"], "existente": True}]
    assert segundo["execution_id"] is None
    outra_competencia = _pedir(cliente, version_id, [_item("5066")], parametros={"competencia": "11/2026"})
    assert outra_competencia["jobs"][0]["existente"] is False
    print(f"\ncenário 4: 2º pedido igual -> job {segundo['jobs'][0]['job_id'][:12]}… existente; outra competência -> job novo")


def test_cenario_4_dois_pedidos_ao_mesmo_tempo_criam_um_job_so(sessao, engine) -> None:
    _, version_id = _automacao_publicada(sessao)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    resultados, barreira = [], threading.Barrier(2)

    def pedir() -> None:
        db = fabrica()
        try:
            fila = build_fila(db)
            barreira.wait()
            r = fila.enfileirar.execute(automation_version_id=version_id, itens=[_item("7000")],
                                        parametros={"competencia": "10/2026"}, prioridade=0, solicitante=None,
                                        now=datetime.now(UTC))
            db.commit()
            resultados.append(r["jobs"][0])
        finally:
            db.close()

    threads = [threading.Thread(target=pedir) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    total = sessao.execute(text("SELECT count(*) FROM task_executions t JOIN execution_items i ON i.task_execution_id = t.id"
                                " WHERE t.automation_version_id = :v AND i.item_key = '7000'"), {"v": version_id}).scalar_one()
    assert total == 1
    assert len({r["job_id"] for r in resultados}) == 1 and sorted(r["existente"] for r in resultados) == [False, True]
    print("\ncenário 4 (simultâneo): 2 pedidos no mesmo instante -> 1 job")


def test_cenario_3_grupo_nunca_se_divide_entre_maquinas(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    _maquina_direta(sessao, automation_id, f"DP-A-{version_id}")
    _maquina_direta(sessao, automation_id, f"DP-B-{version_id}")
    pedido = _pedir(cliente, version_id, [_item("5081"), _item("5076", "5081"), _item("5075", "5081"), _item("5066")])
    assert [j["itens"] for j in pedido["jobs"]] == [["5081", "5076", "5075"], ["5066"]]

    entregues = [e for e in despachar_agora(sessao)["entregues"] if e["job_id"] in {j["job_id"] for j in pedido["jobs"]}]
    grupo = pedido["jobs"][0]["job_id"]
    maquina_do_grupo = next(e["maquina_id"] for e in entregues if e["job_id"] == grupo)
    itens = sessao.execute(text("SELECT item_key FROM execution_items WHERE task_execution_id = :t ORDER BY item_key"),
                           {"t": grupo}).scalars().all()
    tentativas = sessao.execute(text("SELECT DISTINCT machine_id FROM execution_attempts WHERE task_execution_id = :t"),
                                {"t": grupo}).scalars().all()
    assert itens == ["5075", "5076", "5081"] and tentativas == [maquina_do_grupo]
    print(f"\ncenário 3: matriz 5081 + filiais 5076 e 5075 num job só, numa máquina só ({len(entregues)} job(s) entregues)")


def _historico(sessao, version_id: int, ag, item: str, segundos_troca: float) -> None:
    execution_id, job_id = execucao(sessao, version_id, DIA1)
    attempt = tentativa_agente(sessao, job_id, ag)
    r = Roteiro(DIA1 + timedelta(minutes=1)).emitir("execucao.iniciada").etapa("iniciar", 0)
    empresa(r, item, separa=True, centros=1, seg_troca=segundos_troca, seg_por_centro=0)
    r.etapa("aviso", 0).emitir("execucao.concluida", situacao="ok")
    enviar_pelo_agente(sessao, attempt, ag, r.eventos)
    sessao.execute(text("UPDATE task_executions SET status = 'succeeded' WHERE id = :t"), {"t": job_id})
    sessao.execute(text("UPDATE execution_attempts SET status = 'succeeded' WHERE id = :a"), {"a": attempt})
    sessao.commit()


def test_cenario_1_duas_maquinas_cinco_jobs_na_fila_real(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    historico_ag = agente(sessao, maquina(sessao, f"historico-{version_id}"))
    sessao.execute(text("UPDATE agents SET enabled = false WHERE id = :a"), {"a": historico_ag.agent_id})
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE id = :m"), {"m": historico_ag.machine_id})
    sessao.commit()
    minutos = {"8010": 10, "8050": 50, "8030": 30, "8020": 20, "8040": 40}
    for item, m in minutos.items():
        _historico(sessao, version_id, historico_ag, item, m * 60)
    a, _ = _maquina_direta(sessao, automation_id, f"A-{version_id}")
    b, _ = _maquina_direta(sessao, automation_id, f"B-{version_id}")
    pedido = _pedir(cliente, version_id, [_item(i) for i in minutos])
    meus = {j["job_id"] for j in pedido["jobs"]}

    linhas = [j for j in _fila(cliente)["jobs"] if j["job_id"] in meus]
    assert [l["itens"][0] for l in linhas] == ["8050", "8040", "8030", "8020", "8010"]
    inicio = {l["itens"][0]: datetime.fromisoformat(l["inicio_previsto"]) for l in linhas}
    maquina_de = {l["itens"][0]: l["maquina_prevista"] for l in linhas}
    assert {maquina_de["8050"], maquina_de["8040"]} == {a, b}
    assert maquina_de["8030"] == maquina_de["8040"] and maquina_de["8020"] == maquina_de["8050"]
    assert round((inicio["8030"] - inicio["8040"]).total_seconds() / 60) == 40
    assert round((inicio["8020"] - inicio["8050"]).total_seconds() / 60) == 50
    print("\ncenário 1 (fila real, estimativas do histórico):")
    for l in linhas:
        print(f"  {l['posicao']}. empresa {l['itens'][0]} ~{l['estimativa_s'] / 60:.0f} min -> {l['maquina_prevista_nome']}"
              f", início {l['inicio_previsto'][11:16]}, término {l['termino_previsto'][11:16]}")


def test_cenario_5_um_job_de_tela_por_maquina_com_dois_pedidos_simultaneos(sessao, engine) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    mch = maquina(sessao, f"tela-{version_id}")
    _, job_a = execucao(sessao, version_id, AGORA)
    _, job_b = execucao(sessao, version_id, AGORA)
    for job in (job_a, job_b):
        sessao.execute(text("INSERT INTO execution_attempts (id, task_execution_id, attempt_number, status, executor_type,"
                            " executor_id, machine_id) VALUES (:i, :t, 1, 'committed', 'direct', 'x', :m)"),
                       {"i": f"att-{job}", "t": job, "m": mch})
    sessao.commit()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    ganhou, barreira = [], threading.Barrier(2)

    def travar(job: str) -> None:
        db = fabrica()
        try:
            barreira.wait()
            ok = SqlAlchemyQueueReader(db).tentar_trava_de_tela(lock_id=f"lock-{job}", machine_id=mch,
                                                                attempt_id=f"att-{job}", agora=datetime.now(UTC),
                                                                validade=timedelta(hours=1))
            db.commit()
            ganhou.append(ok)
        finally:
            db.close()

    threads = [threading.Thread(target=travar, args=(j,)) for j in (job_a, job_b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sorted(ganhou) == [False, True]
    print("\ncenário 5: 2 travas de tela pedidas no mesmo instante na mesma máquina -> 1 concedida")


def test_cenario_16_direto_e_agente_de_tela_na_mesma_maquina_nunca_juntos(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    mch, instancia = _maquina_direta(sessao, automation_id, f"mista-{version_id}")
    ag = agente(sessao, mch)
    sessao.execute(text("UPDATE agents SET enabled = false WHERE id = :a"), {"a": ag.agent_id})  # Agent fora: vai o direto
    sessao.commit()
    pedido = _pedir(cliente, version_id, [_item("9101"), _item("9102")])
    entregues = [e for e in despachar_agora(sessao)["entregues"] if e["maquina_id"] == mch]
    assert len(entregues) == 1 and entregues[0]["modo"] == "direto"

    # Agent volta: a máquina já tem tela ocupada pelo modo direto, então ele não recebe o 2º job.
    sessao.execute(text("UPDATE agents SET enabled = true, connectivity_status = 'online' WHERE id = :a"), {"a": ag.agent_id})
    sessao.commit()
    segunda = [e for e in despachar_agora(sessao)["entregues"] if e["maquina_id"] == mch]
    assert segunda == []
    from modules.dispatch.infrastructure.repositories import SqlAlchemyResourceLockRepository
    from modules.dispatch.domain.resource_lock import normalize_resource_key
    conflito = SqlAlchemyResourceLockRepository(sessao).active_conflict(normalize_resource_key(f"machine:{mch}:screen"), "maquina_tela")
    assert conflito is not None  # o filtro do Agent (RESOURCE_LOCKED) também vê a trava
    linha = next(j for j in _fila(cliente)["jobs"] if j["job_id"] in {p["job_id"] for p in pedido["jobs"]})
    print(f"\ncenário 16: máquina com Agent e instância direta -> 1 job de tela por vez; o seguinte espera "
          f"(início previsto: {linha['inicio_previsto'] or 'sem previsão'}; motivos: {[m['texto'] for m in linha['motivos']]})")


def _perder(sessao, job: str) -> None:
    """O job fica perdido como o DetectLostAttempts deixa: tentativa e job ``lost``, trava de tela mantida."""
    sessao.execute(text("UPDATE execution_attempts SET status = 'lost', completed_at = now() WHERE task_execution_id = :t"), {"t": job})
    sessao.execute(text("UPDATE task_executions SET status = 'lost', lost_at = now() WHERE id = :t"), {"t": job})
    sessao.commit()


def test_cenario_2_maquina_cai_job_perdido_nao_volta_sozinho(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    mch, instancia = _maquina_direta(sessao, automation_id, f"cai-{version_id}")
    pedido = _pedir(cliente, version_id, [_item("9201")])
    job = pedido["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"] if e["job_id"] == job] == [job]

    # Job perdido (modo agente: o Agent sumiu; no modo direto o silêncio cancela, ver test_comunicacao).
    _perder(sessao, job)
    status = sessao.execute(text("SELECT status FROM task_executions WHERE id = :t"), {"t": job}).scalar_one()
    assert status == "lost"
    for _ in range(3):  # vários ciclos depois, continua perdido: nada volta sozinho
        despachar_agora(sessao)
    sessao.expire_all()
    assert sessao.execute(text("SELECT status FROM task_executions WHERE id = :t"), {"t": job}).scalar_one() == "lost"
    trava = sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                           {"m": mch}).scalar_one()
    assert trava == 1  # a máquina fica travada até a decisão

    decisao = cliente.post(f"/api/v1/fila/jobs/{job}/decisao", json={"decisao": "continuar"})
    assert decisao.status_code == 200 and decisao.json() == {"job_id": job, "status": "queued", "maquina_obrigatoria": mch}
    trava = sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                           {"m": mch}).scalar_one()
    assert trava == 0
    print(f"\ncenário 2: instância sem sinal -> job perdido; 3 ciclos depois continua perdido; "
          f"'continuar' devolve para a mesma máquina ({mch})")


def test_job_perdido_recomecar_do_zero_libera_qualquer_maquina(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    mch, instancia = _maquina_direta(sessao, automation_id, f"recomeca-{version_id}")
    job = _pedir(cliente, version_id, [_item("9301")])["jobs"][0]["job_id"]
    despachar_agora(sessao)
    _perder(sessao, job)
    resposta = cliente.post(f"/api/v1/fila/jobs/{job}/decisao", json={"decisao": "recomecar"})
    assert resposta.json()["maquina_obrigatoria"] is None
    assert cliente.post(f"/api/v1/fila/jobs/{job}/decisao", json={"decisao": "recomecar"}).status_code == 409


def test_cenario_14_instancia_revogada_ou_em_quarentena_nao_recebe_jobs(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    entregues_por_status = {}
    for status in ("revogada", "quarentena"):
        mch, instancia = _maquina_direta(sessao, automation_id, f"{status}-{version_id}")
        sessao.execute(text("UPDATE direct_instances SET status = :s WHERE id = :i"), {"s": status, "i": instancia})
        sessao.commit()
        job = _pedir(cliente, version_id, [_item(f"94{len(entregues_por_status)}")])["jobs"][0]["job_id"]
        entregues_por_status[status] = [e for e in despachar_agora(sessao)["entregues"] if e["job_id"] == job]
    assert entregues_por_status == {"revogada": [], "quarentena": []}
    print("\ncenário 14: instância revogada e em quarentena -> nenhum job entregue")


def test_fim_declarado_no_modo_direto_conclui_e_libera_a_maquina(sessao, cliente) -> None:
    from modules.dispatch.application.use_cases.job_tokens import IssueJobToken
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyJobTokenStore

    automation_id, version_id = _automacao_publicada(sessao)
    mch, instancia = _maquina_direta(sessao, automation_id, f"fim-{version_id}")
    job = _pedir(cliente, version_id, [_item("9501")])["jobs"][0]["job_id"]
    despachar_agora(sessao)
    tentativa = sessao.execute(text("SELECT id FROM execution_attempts WHERE task_execution_id = :t"), {"t": job}).scalar_one()
    token = IssueJobToken(SqlAlchemyJobTokenStore(sessao)).execute(task_execution_id=job, execution_attempt_id=tentativa,
                                                                  direct_instance_id=instancia, now=datetime.now(UTC))
    sessao.commit()
    eventos = Roteiro(AGORA).emitir("execucao.iniciada").emitir("execucao.concluida", situacao="ok").eventos
    resposta = cliente.post(f"/api/v1/direto/jobs/{job}/eventos", json={"eventos": eventos},
                            headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200, resposta.text
    sessao.expire_all()
    estado = sessao.execute(text("SELECT t.status, a.status FROM task_executions t JOIN execution_attempts a"
                                 " ON a.task_execution_id = t.id WHERE t.id = :t"), {"t": job}).one()
    travas = sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                            {"m": mch}).scalar_one()
    assert tuple(estado) == ("succeeded", "succeeded") and travas == 0


def test_fila_mostra_motivos_reordena_e_cancela(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    # Sem nenhuma máquina ativa no banco de teste (as dos outros testes voltam no fim).
    ativas = sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa' RETURNING id")).scalars().all()
    sessao.commit()
    try:
        pedido = _pedir(cliente, version_id, [_item("9601"), _item("9602")])
        ids = [j["job_id"] for j in pedido["jobs"]]
        linhas = {j["job_id"]: j for j in _fila(cliente)["jobs"] if j["job_id"] in ids}
        assert all(any(m["codigo"] == "sem_maquina_compativel" for m in linhas[i]["motivos"]) for i in ids)
    finally:
        sessao.execute(text("UPDATE machines SET status = 'ativa' WHERE id = ANY(:ids)"), {"ids": ativas})
        sessao.commit()

    assert cliente.patch(f"/api/v1/fila/jobs/{ids[1]}", json={"prioridade": 9}).status_code == 200
    ordem = [j["job_id"] for j in _fila(cliente)["jobs"] if j["job_id"] in ids]
    assert ordem == [ids[1], ids[0]]
    assert cliente.post(f"/api/v1/fila/jobs/{ids[0]}/cancelar").json()["status"] == "cancelled"
    assert [j["job_id"] for j in _fila(cliente)["jobs"] if j["job_id"] in ids] == [ids[1]]
    print(f"\nfila: sem máquina -> motivo '{linhas[ids[0]]['motivos'][0]['texto']}'; prioridade 9 passa à frente; "
          "cancelado sai da fila")


def test_despacho_para_agente_libera_o_job_so_para_aquele_agent_com_a_trava_de_tela(sessao, cliente) -> None:
    from modules.dispatch.application.use_cases.scheduler import FindEligibleAgents
    from modules.dispatch.domain.candidate import DispatchCandidate
    from modules.dispatch.infrastructure.repositories import SqlAlchemyReadyTaskRepository

    automation_id, version_id = _automacao_publicada(sessao)
    mch = maquina(sessao, f"agente-{version_id}")
    ag = agente(sessao, mch)
    pedido = _pedir(cliente, version_id, [_item("9701"), _item("9702")])
    ids = [j["job_id"] for j in pedido["jobs"]]

    # Antes do despacho da fila, o Scheduler antigo não pega jobs da fila nova.
    reclamados = {t.id for t in SqlAlchemyReadyTaskRepository(sessao).claim_ready(datetime.now(UTC), 100)}
    sessao.rollback()
    assert not reclamados & set(ids)

    entregues = [e for e in despachar_agora(sessao)["entregues"] if e["job_id"] in ids]
    assert len(entregues) == 1 and entregues[0]["modo"] == "agente" and entregues[0]["executor"] == ag.agent_id
    job = entregues[0]["job_id"]
    status, requisitos = sessao.execute(text("SELECT status, requirements_snapshot FROM task_executions WHERE id = :t"),
                                        {"t": job}).one()
    assert status == "ready"
    assert requisitos["dispatch"]["required_agent_id"] == ag.agent_id
    assert {"key": f"machine:{mch}:screen", "scope": "maquina_tela"} in requisitos["exclusive_resources"]
    outro = [j for j in ids if j != job][0]
    assert sessao.execute(text("SELECT status FROM task_executions WHERE id = :t"), {"t": outro}).scalar_one() == "queued"

    filtro = FindEligibleAgents(None, None, None)
    outro_agent = DispatchCandidate.pending(agent_id="agt_outro", agent_instance_id="agi_outro", worker_id=None,
                                            evaluated_at=datetime.now(UTC))
    recusado = filtro._apply_filters(outro_agent, None, requisitos, set(), datetime.now(UTC))
    assert [r.code for r in recusado.rejection_reasons] == ["NOT_SELECTED_BY_QUEUE"]


def test_fila_traz_nome_da_automacao_e_jobs_perdidos(sessao, cliente) -> None:
    automation_id, version_id = _automacao_publicada(sessao)
    mch, instancia = _maquina_direta(sessao, automation_id, f"nomes-{version_id}")
    job = _pedir(cliente, version_id, [_item("9801")])["jobs"][0]["job_id"]
    espera = _pedir(cliente, version_id, [_item("9802")])["jobs"][0]["job_id"]
    linha = next(j for j in _fila(cliente)["jobs"] if j["job_id"] == espera)
    assert linha["automacao"].startswith("Integração Contábil")
    despachar_agora(sessao)
    _perder(sessao, job)
    perdido = next(p for p in _fila(cliente)["perdidos"] if p["job_id"] == job)
    assert perdido["maquina_nome"] == f"nomes-{version_id}" and perdido["itens"] == ["9801"]


def test_usuario_sem_permissao_nao_ve_job_alheio_nem_quem_ocupa_a_maquina(sessao, cliente) -> None:
    from types import SimpleNamespace

    from modules.access.api.dependencies import get_current_user

    automation_id, version_id = _automacao_publicada(sessao)
    mch, _ = _maquina_direta(sessao, automation_id, f"visivel-{version_id}")
    pedido = _pedir(cliente, version_id, [_item("9601"), _item("9602")])
    despachar_agora(sessao)
    meus = {j["job_id"] for j in pedido["jobs"]}
    admin = _fila(cliente)
    rodando_admin = [r["job_id"] for m in admin["maquinas"] if m["id"] == mch for r in m["rodando"]]
    assert len(rodando_admin) == 1 and rodando_admin[0] in meus

    sem_permissao = SimpleNamespace(id=999_999, role=SimpleNamespace(slug="viewer"), permissions=[], organization_id=None)
    cliente.app.dependency_overrides[get_current_user] = lambda: sem_permissao
    try:
        visao = _fila(cliente)
    finally:
        cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role=SimpleNamespace(slug="admin"))
    assert not meus & {j["job_id"] for j in visao["jobs"]}
    maquina_vista = next(m for m in visao["maquinas"] if m["id"] == mch)
    assert [r["job_id"] for r in maquina_vista["rodando"]] == [None]  # vê que está ocupada, não por qual job


def test_motivo_nomeia_etapas_sem_historico_e_quem_segura_a_fila(sessao, cliente, monkeypatch) -> None:
    from types import SimpleNamespace

    from modules.access.api.dependencies import get_current_user
    from modules.dispatch.api import fila as api_fila

    automacao_a, versao_a = _automacao_publicada(sessao)
    automacao_b, versao_b = _automacao_publicada(sessao)
    mch = maquina(sessao, f"compartilhada-{versao_a}")
    instancia_com_sinal(sessao, instancia_direta(sessao, automacao_a, mch))
    instancia_com_sinal(sessao, instancia_direta(sessao, automacao_b, mch))
    rodando = _pedir(cliente, versao_a, [_item("9701")])["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [rodando]
    esperando = _pedir(cliente, versao_b, [_item("9702")])["jobs"][0]["job_id"]
    nome_a = sessao.execute(text("SELECT name FROM automations WHERE id = :a"), {"a": automacao_a}).scalar_one()

    linha = next(j for j in _fila(cliente)["jobs"] if j["job_id"] == esperando)
    textos = textos_admin = [m["texto"] for m in linha["motivos"]]
    assert f"aguardando o término de {nome_a} (9701), que está sem previsão" in textos
    assert any(t.startswith("etapas Iniciar, Trocar empresa, Rubricas e mais 2 (item 9702) rodando pela primeira vez") for t in textos)
    assert linha["etapas_sem_base"] == ["Iniciar", "Trocar empresa", "Rubricas", "Integração (TXT)", "Aviso"]
    assert all("automation_id" not in m for m in linha["motivos"])

    # Quem vê a automação B mas não a A não fica sabendo o nome de A: o motivo vira genérico.
    monkeypatch.setattr(api_fila, "_pode", lambda _db, _u, automation_id, _acao: automation_id == automacao_b)
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role=SimpleNamespace(slug="viewer"))
    try:
        linha = next(j for j in _fila(cliente)["jobs"] if j["job_id"] == esperando)
    finally:
        cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role=SimpleNamespace(slug="admin"))
    textos = [m["texto"] for m in linha["motivos"]]
    assert "aguardando o término de um job que não tem previsão" in textos
    assert not any(nome_a in t for t in textos)
    print(f"\nmotivos para quem vê as duas automações: {textos_admin}"
          f"\nmotivos para quem só vê a segunda: {textos}")
