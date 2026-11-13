"""Limites do sistema e limpeza automática no PostgreSQL de teste.

Limpeza: o padrão já vale sem configurar (notificações 7 dias), a última medição de cada Agent
fica, o que está pendente fica, regra desligada não apaga, tudo vai à auditoria.
Limites: a API valida a faixa, o início do Portal não regrava o que alguém mudou e cada
limite ligado vale no seu ponto (Agents, agendamento, tempo e repetições, fila).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from modules.fleet.domain.value_objects import hash_secret
from tests.db.semente import agente, automacao, maquina, novo, publicar


def _contar(sessao, sql: str, **p) -> int:
    return int(sessao.execute(text(sql), p).scalar_one())


def _notificacao(sessao, criada_em: datetime) -> str:
    nid = novo("ntf")
    sessao.execute(text("INSERT INTO notifications (id, chave, tipos, titulo, texto, quando, created_at)"
                        " VALUES (:i, :i, '[\"erro\"]', 't', 't', :c, :c)"), {"i": nid, "c": criada_em})
    uid = sessao.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar_one()
    sessao.execute(text("INSERT INTO notification_deliveries (id, notification_id, user_id, email, created_at)"
                        " VALUES (:i, :n, :u, 'a@teste.invalid', :c)"), {"i": novo("ntd"), "n": nid, "u": uid, "c": criada_em})
    return nid


def _medicao(sessao, ag, quando: datetime) -> str:
    sid = novo("snp")
    sessao.execute(text("INSERT INTO agent_resource_snapshots (id, agent_id, agent_instance_id, observed_at)"
                        " VALUES (:i, :a, :ai, :q)"), {"i": sid, "a": ag.agent_id, "ai": ag.instance_id, "q": quando})
    return sid


def _comando(sessao, ag, status: str, criado_em: datetime, sequencia: int) -> str:
    cid = str(uuid.uuid4())
    sessao.execute(text("INSERT INTO agent_commands (id, agent_id, command_sequence, message_type, payload, status, created_at)"
                        " VALUES (:i, :a, :n, 'x', '{}', :s, :c)"),
                   {"i": cid, "a": ag.agent_id, "n": sequencia, "s": status, "c": criado_em})
    return cid


def test_limpeza_do_sistema_com_os_padroes(cliente, sessao) -> None:
    from modules.governance.infrastructure.adapters.limpeza import build_aplicar_limpeza

    agora = datetime.now(UTC)
    velha, nova = _notificacao(sessao, agora - timedelta(days=8)), _notificacao(sessao, agora - timedelta(days=6))
    ag = agente(sessao, maquina(sessao))
    medicoes_velhas = [_medicao(sessao, ag, agora - timedelta(days=d)) for d in (30, 20)]
    ag_parado = agente(sessao, maquina(sessao))
    unica_do_parado = _medicao(sessao, ag_parado, agora - timedelta(days=40))  # a última dele: fica
    recente = _medicao(sessao, ag, agora - timedelta(hours=1))
    concluido = _comando(sessao, ag, "acknowledged", agora - timedelta(days=40), 1)
    pendente = _comando(sessao, ag, "pending", agora - timedelta(days=40), 2)
    sessao.commit()

    feito = build_aplicar_limpeza(sessao).execute()

    assert feito["notificacoes"] >= 1
    ids = set(sessao.execute(text("SELECT id FROM notifications")).scalars())
    assert velha not in ids and nova in ids
    assert _contar(sessao, "SELECT count(*) FROM notification_deliveries WHERE notification_id = :n", n=velha) == 0
    medicoes = set(sessao.execute(text("SELECT id FROM agent_resource_snapshots")).scalars())
    assert not medicoes & set(medicoes_velhas) and {recente, unica_do_parado} <= medicoes
    comandos = set(sessao.execute(text("SELECT id FROM agent_commands")).scalars())
    assert concluido not in comandos and pendente in comandos
    assert _contar(sessao, "SELECT count(*) FROM audit_events WHERE action = 'limpeza.aplicada'"
                           " AND resource_id = 'notificacoes'") >= 1
    tela = cliente.get("/api/v1/governance/limpeza").json()
    linha = next(i for i in tela["itens"] if i["chave"] == "notificacoes")
    assert linha["dias"] == 7 and linha["ultima_limpeza_em"] and linha["total_apagados"] >= 1
    assert "Guardado sempre" in tela["grupos"]


def test_regra_desligada_nao_apaga_e_api_valida(cliente, sessao) -> None:
    from modules.governance.infrastructure.adapters.limpeza import build_aplicar_limpeza

    assert cliente.put("/api/v1/governance/limpeza/notificacoes", json={"dias": 1}).status_code == 422
    assert cliente.put("/api/v1/governance/limpeza/sempre.auditoria", json={"dias": 30}).status_code == 422
    assert cliente.put("/api/v1/governance/limpeza/nao.existe", json={"dias": 30}).status_code == 422
    r = cliente.put("/api/v1/governance/limpeza/notificacoes", json={"dias": None})
    assert r.status_code == 200 and r.json()["dias"] is None and r.json()["personalizado"] is True
    try:
        velha = _notificacao(sessao, datetime.now(UTC) - timedelta(days=60))
        sessao.commit()
        build_aplicar_limpeza(sessao).execute()
        assert velha in set(sessao.execute(text("SELECT id FROM notifications")).scalars())
    finally:
        volta = cliente.put("/api/v1/governance/limpeza/notificacoes", json={"voltar_ao_padrao": True})
        assert volta.status_code == 200 and volta.json()["dias"] == 7
    assert _contar(sessao, "SELECT count(*) FROM audit_events WHERE action = 'limpeza.prazo_definido'") >= 2


def test_limites_api_e_inicio_do_portal_nao_regrava(cliente, sessao) -> None:
    from modules.governance.application.use_cases import BootstrapGovernanceDefaults
    from modules.governance.infrastructure.adapters import build_governance_adapters

    tela = cliente.get("/api/v1/governance/limites").json()
    gateway = next(i for i in tela["itens"] if i["chave"] == "gateway.max_message_bytes")
    assert gateway["origem"] == "arquivo" and gateway["variavel_de_ambiente"]
    assert cliente.put("/api/v1/governance/limites/gateway.max_message_bytes", json={"valor": 4096}).status_code == 422
    assert cliente.put("/api/v1/governance/limites/execution.max_concurrent", json={"valor": 0}).status_code == 422
    assert cliente.put("/api/v1/governance/system-limits/execution.max_concurrent",
                       json={"value": 0, "unit": "count"}).status_code == 422  # a API antiga valida igual
    r = cliente.put("/api/v1/governance/limites/package.max_size_mb", json={"valor": 321})
    assert r.status_code == 200 and r.json()["valor"] == 321 and r.json()["personalizado"] is True
    try:
        g = build_governance_adapters(sessao)
        BootstrapGovernanceDefaults(g.governance, g.transaction).execute()  # o que roda a cada início
        assert _contar(sessao, "SELECT value FROM system_limits WHERE key = 'package.max_size_mb'"
                               " AND organization_id IS NULL") == 321
    finally:
        cliente.put("/api/v1/governance/limites/package.max_size_mb", json={"valor": 200})


def _definir_limite(sessao, chave: str, valor: int) -> None:
    from modules.governance.domain.configuracoes import limite
    from modules.governance.infrastructure.limites import esquecer_cache
    from modules.governance.infrastructure.repositories.sqlalchemy_configuracoes import SqlAlchemyConfiguracoes

    SqlAlchemyConfiguracoes(sessao).gravar_limite(limite(chave), valor)
    sessao.commit()
    esquecer_cache()


def test_tempo_e_repeticoes_respeitam_o_teto(sessao) -> None:
    from modules.dispatch.infrastructure.repositories.sqlalchemy_dispatch import SqlAlchemyAutomationVersionReader

    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    sessao.execute(text("UPDATE automation_versions SET manifest_id = NULL, manifest = CAST(:m AS jsonb) WHERE id = :v"),
                   {"m": '{"execution": {"timeout_seconds": 90000, "max_retries": 9}}', "v": version_id})
    sessao.commit()
    _definir_limite(sessao, "execution.max_timeout_seconds", 3600)
    _definir_limite(sessao, "execution.max_retries", 2)
    try:
        foto = SqlAlchemyAutomationVersionReader(sessao).get_published_snapshot(version_id)
        assert foto is not None
        assert foto.timeout_seconds == 3600 and foto.timeout_policy["execution_timeout_seconds"] == 3600
        assert foto.retry_policy["max_attempts"] == 3
    finally:
        _definir_limite(sessao, "execution.max_timeout_seconds", 14400)
        _definir_limite(sessao, "execution.max_retries", 3)


def test_limite_de_agents_e_intervalo_minimo(cliente, sessao) -> None:
    from modules.fleet.application.use_cases import RegisterAgent
    from modules.fleet.domain.errors import AgentRegistrationError
    from modules.fleet.infrastructure.adapters import build_fleet_adapters

    a = build_fleet_adapters(sessao)
    existentes = len(a.agents.list())
    caso = RegisterAgent(a.agents, a.registration_tokens, a.credentials, a.configurations, None, None, a.transaction,
                         max_agents=lambda: existentes)
    sessao.execute(text("INSERT INTO agent_registration_tokens (id, token_hash, status, expires_at)"
                        " VALUES ('art_lim', :h, 'active', now() + interval '1 hour')"),
                   {"h": hash_secret("tok-limite")})
    sessao.commit()
    try:
        caso.execute("tok-limite", {"local_identity": "nova-maquina", "hostname": "nova"})
        raise AssertionError("deveria recusar acima do limite")
    except AgentRegistrationError as exc:
        assert "limite" in str(exc).lower()

    automation_id, _ = automacao(sessao)
    corpo = {"name": "a cada 2 min", "automation_id": automation_id, "schedule_type": "interval", "interval_seconds": 120,
             "timezone": "America/Sao_Paulo"}
    _definir_limite(sessao, "schedule.min_interval_seconds", 300)
    try:
        r = cliente.post("/api/v1/schedules", json=corpo)
        assert r.status_code == 422 and "300" in r.text, r.text
    finally:
        _definir_limite(sessao, "schedule.min_interval_seconds", 60)


def test_execucoes_ao_mesmo_tempo_seguram_a_fila(cliente, sessao) -> None:
    from modules.dispatch.api.fila import despachar_agora
    from modules.dispatch.infrastructure.repositories.sqlalchemy_queue_view import SqlAlchemyQueueReader
    from tests.db.semente import instancia_com_sinal, instancia_direta

    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa'"))
    sessao.execute(text("UPDATE task_executions SET status = 'cancelled' WHERE status IN ('queued', 'ready')"
                        " AND enqueue_batch_id IS NOT NULL"))
    sessao.commit()
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    for nome in ("LIM-A", "LIM-B", "LIM-C"):
        instancia_com_sinal(sessao, instancia_direta(sessao, automation_id, maquina(sessao, f"{nome}-{version_id}")))
    pedido = cliente.post("/api/v1/fila/execucoes", json={
        "automation_version_id": version_id, "parametros": {"competencia": "10/2026"}, "prioridade": 0,
        "itens": [{"chave": c, "rotulo": c, "grupo": c, "configuracao": {}} for c in ("L1", "L2", "L3")]})
    assert pedido.status_code == 201, pedido.text

    from modules.governance.infrastructure.limites import ler_limite

    anterior = ler_limite(sessao, "execution.max_concurrent")
    ocupadas = SqlAlchemyQueueReader(sessao).em_andamento()
    _definir_limite(sessao, "execution.max_concurrent", ocupadas + 1)
    try:
        entregues = despachar_agora(sessao)["entregues"]
        assert len(entregues) == 1  # três máquinas livres, mas só uma vaga no limite
        assert despachar_agora(sessao)["entregues"] == []
        _definir_limite(sessao, "execution.max_concurrent", ocupadas + 3)
        assert len(despachar_agora(sessao)["entregues"]) == 2  # mais vagas: os outros dois saem
    finally:
        _definir_limite(sessao, "execution.max_concurrent", anterior)
