"""Histórico: o resumo do período e o filtro "últimos N dias", só com o que a pessoa vê."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.db.semente import automacao, maquina
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _conceder, _usuario
from tests.db.test_painel_rapido import _rodou


def test_resumo_e_periodo(cliente, sessao) -> None:
    a1, v1 = automacao(sessao)
    a2, v2 = automacao(sessao)
    m = maquina(sessao, f"HIST-{uuid.uuid4().hex[:4]}")
    agora = datetime.now(UTC)
    _rodou(sessao, v1, m, a1, agora - timedelta(minutes=50), [])
    _rodou(sessao, v1, m, a1, agora - timedelta(days=3), [])
    falha = _rodou(sessao, v1, m, a1, agora - timedelta(minutes=20), [])
    sessao.execute(text("UPDATE orchestration_executions SET status = 'failed', started_at = :i WHERE id = :e"),
                   {"i": agora - timedelta(minutes=30), "e": falha})
    _rodou(sessao, v2, m, a2, agora - timedelta(minutes=10), [])
    sessao.execute(text("UPDATE orchestration_executions SET started_at = completed_at - interval '10 minutes'"
                        " WHERE status = 'succeeded' AND started_at IS NULL"))
    sessao.commit()

    hoje = cliente.get("/api/v1/historico/resumo", params={"dias": 2, "automacao": a1}).json()  # 2: não depende da hora do teste
    assert (hoje["total"], hoje["concluidas"], hoje["com_falha"]) == (2, 1, 1)
    assert hoje["duracao_media_s"] == 600  # só as que deram certo entram na média
    semana = cliente.get("/api/v1/historico/resumo", params={"dias": 7, "automacao": a1}).json()
    assert (semana["total"], semana["concluidas"]) == (3, 2)
    so_hoje = cliente.get("/api/v1/historico", params={"dias": 2, "automacao": a1}).json()["execucoes"]
    assert len(so_hoje) == 2

    pessoa, _ = _usuario(sessao, "sem_permissao")
    _conceder(sessao, a2, pessoa, ["ver_execucoes"])
    with como(cliente, pessoa, "sem_permissao"):
        dela = cliente.get("/api/v1/historico/resumo", params={"dias": 2}).json()
        assert dela["total"] == 1 and dela["concluidas"] == 1  # só a automação que ela vê
    assert cliente.get("/api/v1/historico/resumo", params={"dias": 0}).status_code == 422
