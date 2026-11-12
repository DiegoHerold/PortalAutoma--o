"""Etapa 3 (12/11/2026): a tela de Usuários mostra o que a pessoa acessa (telas pelo papel,
automações pelos times, exceções) e não pendura mais permissão por categoria na pessoa."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from tests.db.semente import automacao
from tests.db.test_fase6_notificacoes_retencao import _usuario
from tests.db.test_permissoes_para_times import _categoria


def test_resumo_do_acesso_da_pessoa(cliente, sessao) -> None:
    ana, _ = _usuario(sessao, "operator")
    org = sessao.execute(text("SELECT id FROM access_organizations ORDER BY id LIMIT 1")).scalar()
    if org is None:
        org = sessao.execute(text("INSERT INTO access_organizations (key, name, status) VALUES ('default', 'Padrão', 'active') "
                                  "RETURNING id")).scalar_one()
    folha = _categoria(sessao)
    automation_id, _ = automacao(sessao)
    sessao.commit()
    time = cliente.post("/api/v1/teams", json={"organization_id": org, "key": f"f-{uuid.uuid4().hex[:6]}", "name": "Folha"}).json()
    cliente.post(f"/api/v1/teams/{time['id']}/membros", json={"usuarios": [ana]})
    cliente.put(f"/api/v1/teams/{time['id']}/categorias", json={"categorias": [{"category_id": folha, "can_execute": True}]})
    assert cliente.put(f"/api/v1/automations/{automation_id}/acessos", json={"user_id": ana, "acoes": ["controlar"]}).status_code == 200

    resumo = cliente.get(f"/api/v1/acesso/pessoas/{ana}")
    assert resumo.status_code == 200, resumo.text
    r = resumo.json()
    assert r["papel"]["slug"] == "operator"
    assert {"chave": "historico", "nome": "Histórico", "grupo": "Monitorar", "nivel": "ver"} in r["papel"]["telas"]
    assert [t["nome"] for t in r["times"]] == ["Folha"]
    assert r["times"][0]["categorias"][0] | {"categoria": None} == {"categoria": None, "ver": True, "executar": True,
                                                                     "editar": False, "publicar": False}
    assert r["excecoes"][0]["automation_id"] == automation_id and "controlar" in r["excecoes"][0]["acoes"]
    assert r["permissoes_soltas"] is False
    lista = cliente.get("/api/v1/acesso/pessoas").json()["times"]
    assert [t["nome"] for t in lista[str(ana)]] == ["Folha"]
    assert cliente.get("/api/v1/acesso/pessoas/999999").status_code == 404

    # Pendurar permissão por categoria direto na pessoa não existe mais.
    antiga = cliente.put(f"/api/v1/users/{ana}/permissions", json={"permissions": []})
    assert antiga.status_code == 410 and "times" in antiga.text
    print("\netapa 3: resumo com telas do papel, times com categorias, exceção na automação; permissão solta desligada (410)")
