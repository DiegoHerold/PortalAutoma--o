"""Times (membros e permissões por categoria e por automação) e apagar uma máquina, no PostgreSQL.

As permissões do time são conferidas com login de verdade (token), não com usuário injetado:
é no login que o Portal soma o que os times dão.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from tests.db.semente import automacao, execucao, instancia_direta, maquina, tentativa_direta
from tests.db.test_fase6_notificacoes_retencao import _usuario

SENHA = "Senha-de-teste-1"


@contextlib.contextmanager
def com_login(cliente, email: str):
    """Tira o usuário injetado e usa o token do login real."""
    from modules.access.api.dependencies import get_current_user

    anterior = cliente.app.dependency_overrides.pop(get_current_user)
    try:
        r = cliente.post("/api/v1/auth/login", json={"email": email, "password": SENHA})
        assert r.status_code == 200, r.text
        yield {"Authorization": f"Bearer {r.json()['access_token']}"}
    finally:
        cliente.app.dependency_overrides[get_current_user] = anterior


def _pessoa(sessao) -> tuple[int, str]:
    from modules.access.infrastructure.hashing.passwords import PasslibPasswordHasher

    uid, email = _usuario(sessao, "sem_permissao")
    sessao.execute(text("UPDATE users SET password_hash = :h WHERE id = :i"), {"h": PasslibPasswordHasher().hash(SENHA), "i": uid})
    sessao.commit()
    return uid, email


def _auditoria(sessao, acao: str) -> list[str]:
    sessao.expire_all()
    return [r for (r,) in sessao.execute(text("SELECT resource_id FROM audit_events WHERE action = :a ORDER BY occurred_at"), {"a": acao})]


def test_time_da_permissoes_por_categoria_e_por_automacao_aos_membros(cliente, sessao) -> None:
    automation_id, _ = automacao(sessao)
    categoria = sessao.execute(text("SELECT category_id FROM automations WHERE id = :a"), {"a": automation_id}).scalar_one()
    org = sessao.execute(text("INSERT INTO access_organizations (key, name) VALUES (:k, 'Org times') RETURNING id"),
                         {"k": f"org-{uuid.uuid4().hex[:6]}"}).scalar_one()
    sessao.commit()
    uid, email = _pessoa(sessao)
    base = f"/api/v1/automations/{automation_id}"

    with com_login(cliente, email) as cab:  # sem time: não vê
        assert cliente.get(base, headers=cab).status_code == 403
        assert cliente.get(f"{base}/acessos/minhas", headers=cab).json()["acoes"] == []

    time = cliente.post("/api/v1/teams", json={"organization_id": org, "key": f"folha-{uuid.uuid4().hex[:4]}", "name": "Folha"}).json()
    tid = time["id"]
    assert cliente.post(f"/api/v1/teams/{tid}/membros", json={"usuarios": [uid, 999999]}).status_code == 404  # nada entra
    assert cliente.get(f"/api/v1/teams/{tid}/detalhes").json()["membros"] == []
    assert cliente.post(f"/api/v1/teams/{tid}/membros", json={"usuarios": "x"}).status_code == 422
    membros = cliente.post(f"/api/v1/teams/{tid}/membros", json={"usuarios": [uid, uid]}).json()["membros"]
    assert [m["id"] for m in membros] == [uid]
    cats = cliente.put(f"/api/v1/teams/{tid}/categorias", json={"categorias": [{"category_id": categoria, "can_execute": True}]})
    assert cats.json()["categorias"][0] | {"categoria": None} == {"category_id": categoria, "categoria": None,
                                                                   "can_view": True, "can_execute": True}
    assert cliente.put(f"/api/v1/teams/{tid}/categorias", json={"categorias": [{"category_id": 999999, "can_view": True}]}).status_code == 404
    acesso = cliente.put(f"{base}/acessos", json={"team_id": tid, "acoes": ["ver_telas_e_logs"]})
    assert acesso.status_code == 200, acesso.text
    detalhes = cliente.get(f"/api/v1/teams/{tid}/detalhes").json()
    assert [(a["automation_id"], a["acoes"]) for a in detalhes["automacoes"]] == [(automation_id, ["ver_telas_e_logs"])]
    assert "controlar" in detalhes["acoes_possiveis"]

    with com_login(cliente, email) as cab:  # membro: ganha o do time
        assert cliente.get(base, headers=cab).status_code == 200
        me = cliente.get("/api/v1/auth/me", headers=cab).json()
        assert [(p["category_id"], p["can_view"], p["can_execute"]) for p in me["permissions"]] == [(categoria, True, True)]
        assert set(cliente.get(f"{base}/acessos/minhas", headers=cab).json()["acoes"]) >= {"ver_telas_e_logs", "executar"}
        assert cliente.get(f"/api/v1/teams/{tid}/detalhes", headers=cab).status_code == 403  # membro não administra

    cliente.put(f"/api/v1/teams/{tid}", json={"organization_id": org, "key": time["key"], "name": "Folha", "status": "disabled"})
    with com_login(cliente, email) as cab:  # time desabilitado: não dá nada
        assert cliente.get(base, headers=cab).status_code == 403
    cliente.put(f"/api/v1/teams/{tid}", json={"organization_id": org, "key": time["key"], "name": "Folha", "status": "active"})

    assert cliente.delete(f"/api/v1/teams/{tid}/membros/{uid}").json()["membros"] == []
    assert cliente.delete(f"/api/v1/teams/{tid}/membros/{uid}").status_code == 404
    with com_login(cliente, email) as cab:  # saiu do time: perde
        assert cliente.get(base, headers=cab).status_code == 403

    # No cadastro do usuário: os times dele.
    assert cliente.put(f"/api/v1/users/{uid}/times", json={"times": [tid, 999999]}).status_code == 404
    assert [t["id"] for t in cliente.put(f"/api/v1/users/{uid}/times", json={"times": [tid]}).json()["times"]] == [tid]
    assert [t["nome"] for t in cliente.get(f"/api/v1/users/{uid}/times").json()["times"]] == ["Folha"]
    assert cliente.put(f"/api/v1/users/{uid}/times", json={"times": []}).json()["times"] == []
    assert cliente.put(f"/api/v1/users/{uid}/times", json={}).status_code == 422

    assert _auditoria(sessao, "time.membros.adicionados") == [str(tid)]
    assert _auditoria(sessao, "time.membro.removido") == [str(tid)]
    assert _auditoria(sessao, "time.categorias.definidas") == [str(tid)]
    assert _auditoria(sessao, "usuario.times.definidos") == [str(uid), str(uid)]
    print("\ntimes: sem time 403; membro ganha ver/executar da categoria e a concessão da automação; time desabilitado"
          " ou membro removido perde; times pelo cadastro do usuário; tudo auditado")


def test_apagar_maquina_avisa_os_vinculos_e_so_apaga_confirmando(cliente, sessao) -> None:
    automation_id, version_id = automacao(sessao)
    nome = f"MAQ-{uuid.uuid4().hex[:6]}"
    mch = maquina(sessao, nome)
    instancia = instancia_direta(sessao, automation_id, mch)
    _, job = execucao(sessao, version_id, datetime.now(UTC))
    sessao.execute(text("UPDATE task_executions SET status = 'queued', required_machine_id = :m WHERE id = :j"), {"m": mch, "j": job})
    sessao.commit()

    vinculos = cliente.get(f"/api/v1/maquinas/{mch}/vinculos").json()
    assert vinculos["maquina"] == {"id": mch, "nome": nome} and vinculos["fila"] == 1 and vinculos["rodando"] == 0
    assert [(a["instancia_id"], a["situacao"]) for a in vinculos["automacoes"]] == [(instancia, "aprovada")]

    sem_confirmar = cliente.delete(f"/api/v1/maquinas/{mch}")
    assert sem_confirmar.status_code == 409
    assert sem_confirmar.json()["error"]["details"]["vinculos"]["fila"] == 1
    assert mch in [m["id"] for m in cliente.get("/api/v1/maquinas").json()["maquinas"]]  # nada mudou

    apagada = cliente.delete(f"/api/v1/maquinas/{mch}", params={"confirmar": "true"})
    assert apagada.json() == {"id": mch, "nome": nome, "automacoes_sem_maquina": 1, "agents_sem_maquina": 0, "jobs_liberados": 1}
    sessao.expire_all()
    assert sessao.execute(text("SELECT machine_id, status FROM direct_instances WHERE id = :i"), {"i": instancia}).one() == (None, "pendente")
    assert sessao.execute(text("SELECT required_machine_id FROM task_executions WHERE id = :j"), {"j": job}).scalar_one() is None
    assert sessao.execute(text("SELECT status FROM machines WHERE id = :m"), {"m": mch}).scalar_one() == "removida"
    assert mch not in [m["id"] for m in cliente.get("/api/v1/maquinas").json()["maquinas"]]
    assert cliente.get(f"/api/v1/maquinas/{mch}/vinculos").status_code == 404
    assert cliente.delete(f"/api/v1/maquinas/{mch}", params={"confirmar": "true"}).status_code == 404
    assert cliente.post("/api/v1/maquinas", json={"nome": nome}).status_code == 201  # o nome ficou livre
    assert cliente.post("/api/v1/maquinas", json={"nome": nome}).status_code == 409
    assert _auditoria(sessao, "maquina.removida") [-1] == mch

    # Sem vínculo: apaga direto. Com execução rodando: nunca, nem confirmando.
    livre = maquina(sessao, f"LIVRE-{uuid.uuid4().hex[:6]}")
    assert cliente.delete(f"/api/v1/maquinas/{livre}").status_code == 200
    ocupada = maquina(sessao, f"OCUPADA-{uuid.uuid4().hex[:6]}")
    outra = instancia_direta(sessao, automation_id, ocupada)
    _, job2 = execucao(sessao, version_id, datetime.now(UTC))
    tentativa_direta(sessao, job2, outra, ocupada)
    recusa = cliente.delete(f"/api/v1/maquinas/{ocupada}", params={"confirmar": "true"})
    assert recusa.status_code == 409 and "rodando" in recusa.text
    assert ocupada in [m["id"] for m in cliente.get("/api/v1/maquinas").json()["maquinas"]]
    print(f"\nmáquina: vínculos listados (1 automação, 1 job na fila); sem confirmar 409; confirmada -> instância"
          f" pendente, job liberado, nome livre; rodando nunca apaga")
