"""Auditoria completa no PostgreSQL, com login de verdade: toda alteração fica registrada e ligada
ao evento de negócio da mesma ação; telas abertas; linha do tempo por pessoa, por dia e por ação."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text

from tests.db.test_times_e_maquinas import com_login, _pessoa
from tests.db.test_fase6_notificacoes_retencao import _usuario

API = "/api/v1/governance/auditoria"


def _admin_com_senha(sessao) -> tuple[int, str]:
    uid, email = _pessoa(sessao)
    admin = sessao.execute(text("SELECT id FROM roles WHERE slug = 'admin' ORDER BY id LIMIT 1")).scalar()
    if admin is None:
        _usuario(sessao, "admin")
        admin = sessao.execute(text("SELECT id FROM roles WHERE slug = 'admin' ORDER BY id LIMIT 1")).scalar()
    sessao.execute(text("UPDATE users SET role_id = :r WHERE id = :u"), {"r": admin, "u": uid})
    sessao.commit()
    return uid, email


def test_toda_alteracao_fica_registrada_e_ligada_a_mesma_acao(cliente, sessao) -> None:
    uid, email = _admin_com_senha(sessao)
    nome = f"AUD-{uuid.uuid4().hex[:6]}"
    with com_login(cliente, email) as cab:
        r = cliente.post("/api/v1/maquinas", json={"nome": nome}, headers={**cab, "x-request-id": "req_teste_maquina"})
        assert r.status_code == 201 and r.headers["x-request-id"] == "req_teste_maquina"
        maquina = r.json()["id"]
        # alteração recusada também fica registrada (com o status)
        assert cliente.post("/api/v1/maquinas", json={"nome": nome}, headers=cab).status_code == 409
        # Abrir telas não é mais registrado; o registro antigo fica só nos técnicos.
        assert cliente.post(f"{API}/tela", json={"caminho": "/historico"}, headers=cab).status_code in (404, 405)
        sessao.execute(text("INSERT INTO audit_events (id, actor_type, actor_id, action, resource_type, resource_id,"
                            " occurred_at) VALUES (:i, 'user', :u, 'tela.aberta', 'tela', '/historico', now())"),
                       {"i": f"aud_{uuid.uuid4().hex}", "u": str(uid)})
        sessao.commit()

        mesma = cliente.get(f"{API}/eventos", params={"correlacao": "req_teste_maquina"}, headers=cab).json()["eventos"]
        assert sorted(e["acao"] for e in mesma) == ["api.post", "maquina.cadastrada"]  # o negócio e o técnico, ligados
        negocio = next(e for e in mesma if e["acao"] == "maquina.cadastrada")
        assert negocio["recurso_id"] == maquina and negocio["ator_nome"] and negocio["ator_email"] == email
        assert negocio["ip"] and negocio["tipo"] == "alteracao"

        minhas = cliente.get(f"{API}/eventos", params={"usuario": str(uid)}, headers=cab).json()["eventos"]
        acoes = [e["acao"] for e in minhas]
        # sem "tecnicos": o api.post da criação some (tem o evento de negócio); o do 409 fica (não tem)
        assert acoes.count("maquina.cadastrada") == 1 and acoes.count("api.post") == 1
        recusa = next(e for e in minhas if e["acao"] == "api.post")
        assert recusa["detalhes"]["status"] == 409 and recusa["detalhes"]["rota"] == "/api/v1/maquinas"
        assert "tela.aberta" not in acoes
        assert "login_succeeded" in acoes
        com_tecnicos = cliente.get(f"{API}/eventos", params={"usuario": str(uid), "tecnicos": "true"}, headers=cab).json()["eventos"]
        assert [e["acao"] for e in com_tecnicos].count("api.post") == 2
        assert [e["acao"] for e in com_tecnicos].count("tela.aberta") == 1

        acessos = cliente.get(f"{API}/eventos", params={"usuario": str(uid), "tipo": "acesso"}, headers=cab).json()["eventos"]
        assert {e["acao"] for e in acessos} == {"login_succeeded"}
        hoje = date.today().isoformat()
        assert cliente.get(f"{API}/eventos", params={"usuario": str(uid), "de": "2000-01-01", "ate": "2000-01-02"},
                           headers=cab).json()["eventos"] == []
        assert cliente.get(f"{API}/eventos", params={"usuario": str(uid), "de": hoje, "ate": hoje}, headers=cab).json()["eventos"]

        # histórico de um item: tudo o que aconteceu com esta máquina
        do_item = cliente.get(f"{API}/eventos", params={"recurso_tipo": "machine", "recurso_id": maquina}, headers=cab).json()["eventos"]
        assert [e["acao"] for e in do_item] == ["maquina.cadastrada"]

        por_pessoa = cliente.get(f"{API}/grupos", params={"por": "usuario"}, headers=cab).json()["grupos"]
        eu = next(g for g in por_pessoa if g["chave"] == str(uid))
        assert eu["email"] == email and eu["total"] >= 3  # entrou, cadastrou a máquina e a recusa (telas não contam)
        por_dia = cliente.get(f"{API}/grupos", params={"por": "dia", "usuario": str(uid)}, headers=cab).json()["grupos"]
        assert por_dia[0]["chave"] == hoje
        por_acao = {g["chave"]: g["total"] for g in cliente.get(f"{API}/grupos", params={"por": "acao", "usuario": str(uid)}, headers=cab).json()["grupos"]}
        assert "tela.aberta" not in por_acao and por_acao["maquina.cadastrada"] == 1
        assert cliente.get(f"{API}/grupos", params={"por": "mes"}, headers=cab).status_code == 422
        assert any(p["id"] == str(uid) for p in cliente.get(f"{API}/pessoas", headers=cab).json()["pessoas"])

    # quem não tem audit.read não lê
    _, outro = _pessoa(sessao)
    with com_login(cliente, outro) as cab:
        assert cliente.get(f"{API}/eventos", headers=cab).status_code == 403
    print("\nauditoria: criação ligada ao registro técnico pela mesma ação; recusa (409) registrada; telas abertas não entram;"
          " filtros por pessoa, tipo, período e item; grupos por pessoa, dia e ação")
