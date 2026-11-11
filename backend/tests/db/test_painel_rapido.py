"""Painel prático: as últimas automações (uma linha por automação, filtro por máquina, só o que a
pessoa vê) e as automações que ela pode executar, no PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.db.semente import automacao, execucao, instancia_direta, maquina, tentativa_direta
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _conceder, _usuario


def _rodou(sessao, version_id: int, machine_id: str, automation_id: int, quando: datetime, itens: list[str]) -> str:
    execution_id, job = execucao(sessao, version_id, quando)
    tentativa_direta(sessao, job, instancia_direta(sessao, automation_id, machine_id), machine_id)
    for chave in itens:
        sessao.execute(text("INSERT INTO execution_items (id, execution_id, task_execution_id, automation_id, item_key, label,"
                            " configuration, work_signature, status) VALUES (:i, :e, :t, :a, :k, :k, '{}', '', 'ok')"),
                       {"i": f"itm_{uuid.uuid4().hex[:12]}", "e": execution_id, "t": job, "a": automation_id, "k": chave})
    sessao.execute(text("UPDATE orchestration_executions SET status = 'succeeded', completed_at = :c WHERE id = :e"),
                   {"c": quando, "e": execution_id})
    sessao.commit()
    return execution_id


def test_ultimas_automacoes_por_maquina_e_executaveis(cliente, sessao) -> None:
    agora = datetime.now(UTC) + timedelta(days=1)  # mais novas que as dos outros testes do banco
    a1, v1 = automacao(sessao)
    a2, v2 = automacao(sessao)
    a3, v3 = automacao(sessao)
    m1, m2 = maquina(sessao, f"PAINEL-A-{uuid.uuid4().hex[:4]}"), maquina(sessao, f"PAINEL-B-{uuid.uuid4().hex[:4]}")
    _rodou(sessao, v1, m1, a1, agora - timedelta(hours=3), ["5081"])
    nova_a1 = _rodou(sessao, v1, m1, a1, agora - timedelta(hours=1), ["5076", "5081"])
    _rodou(sessao, v2, m2, a2, agora - timedelta(hours=2), ["7310"])
    _rodou(sessao, v3, m2, a3, agora - timedelta(minutes=30), [])
    sessao.execute(text("UPDATE automations SET status = 'archived' WHERE id = :a"), {"a": a3})  # arquivada não volta
    sessao.commit()

    tudo = cliente.get("/api/v1/painel/recentes").json()
    ids = [a["automation_id"] for a in tudo["automacoes"]]
    assert ids[:2] == [a1, a2] and a3 not in ids  # uma por automação, da mais nova; a 3ª vaga pode ser de outro teste
    primeira = tudo["automacoes"][0]
    assert primeira["ultima"]["execucao_id"] == nova_a1 and primeira["ultima"]["itens"] == ["5076", "5081"]
    assert primeira["ultima"]["status"] == "succeeded" and primeira["pode_executar"] is True
    assert len(primeira["ultima"]["maquinas"]) == 1 and primeira["ultima"]["maquinas"][0].startswith("PAINEL-A")
    assert {m1, m2} <= {m["id"] for m in tudo["maquinas"]}
    so_b = cliente.get("/api/v1/painel/recentes", params={"maquina": m2}).json()["automacoes"]
    assert [a["automation_id"] for a in so_b] == [a2]
    assert cliente.get("/api/v1/painel/recentes", params={"limite": 1}).json()["automacoes"][0]["automation_id"] == a1

    # Quem só vê a2 recebe só a2, e sem poder executar; com "executar", pode.
    pessoa, _ = _usuario(sessao, "sem_permissao")
    _conceder(sessao, a2, pessoa, ["ver_execucoes"])
    with como(cliente, pessoa, "sem_permissao"):
        vistas = cliente.get("/api/v1/painel/recentes").json()["automacoes"]
        assert [(a["automation_id"], a["pode_executar"]) for a in vistas] == [(a2, False)]
        assert cliente.get("/api/v1/painel/executaveis").json()["automacoes"] == []
    _conceder(sessao, a1, pessoa, ["executar"])
    with como(cliente, pessoa, "sem_permissao"):
        assert [a["id"] for a in cliente.get("/api/v1/painel/executaveis").json()["automacoes"]] == [a1]
        assert [a["automation_id"] for a in cliente.get("/api/v1/painel/recentes").json()["automacoes"]] == [a1, a2]
    ids = [a["id"] for a in cliente.get("/api/v1/painel/executaveis").json()["automacoes"]]
    assert a1 in ids and a2 in ids and a3 not in ids  # admin: todas, menos a arquivada
    print("\npainel: uma linha por automação (a mais recente), filtro por máquina, arquivada fora,"
          " só o que a pessoa vê; executáveis respeitam 'executar'")
