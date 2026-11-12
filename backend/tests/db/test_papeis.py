"""Papéis globais (12/11/2026): só o admin cria, muda as abas e apaga; aba desligada some do
menu e, quando a permissão é só dela, a API também recusa. Login de verdade (token)."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from tests.db.test_auditoria_completa import _admin_com_senha
from tests.db.test_times_e_maquinas import _pessoa, com_login

PERMISSOES = ("execution.read", "audit.read", "admin.roles", "schedule.read", "automation.read")


def _garantir_permissoes(sessao) -> None:
    for chave in PERMISSOES:
        sessao.execute(text("INSERT INTO permissions (key) VALUES (:k) ON CONFLICT (key) DO NOTHING"), {"k": chave})
    sessao.commit()


def _com_papel(sessao, papel_id: int) -> tuple[int, str]:
    uid, email = _pessoa(sessao)
    sessao.execute(text("UPDATE users SET role_id = :r WHERE id = :u"), {"r": papel_id, "u": uid})
    sessao.commit()
    return uid, email


def test_crud_de_papeis_e_abas_que_tiram_o_acesso(cliente, sessao) -> None:
    _garantir_permissoes(sessao)
    _, admin = _admin_com_senha(sessao)
    nome = f"Analista Fiscal {uuid.uuid4().hex[:4]}"
    with com_login(cliente, admin) as cab:
        catalogo = cliente.get("/api/v1/papeis/abas", headers=cab).json()["abas"]
        assert {"chave": "/audit", "rotulo": "Auditoria", "grupo": "Segurança"} in catalogo
        criado = cliente.post("/api/v1/papeis", json={"nome": nome, "descricao": "Confere a folha",
                                                      "abas": ["/audit", "/historico"]}, headers=cab)
        assert criado.status_code == 201, criado.text
        papel = criado.json()
        assert papel["abas"] == ["/historico", "/audit"]  # na ordem do menu
        assert papel["slug"].startswith("analista-fiscal") and papel["pode_apagar"] and not papel["sistema"]
        gravadas = set(sessao.execute(text("SELECT permission_key FROM role_permissions WHERE role_id = :r"),
                                      {"r": papel["id"]}).scalars())
        assert {"execution.read", "audit.read"} <= gravadas  # ligar a aba dá a leitura dela
        assert cliente.post("/api/v1/papeis", json={"nome": "X", "abas": ["/inexistente"]}, headers=cab).status_code == 422

    _, pessoa = _com_papel(sessao, papel["id"])
    with com_login(cliente, pessoa) as cab:
        eu = cliente.get("/api/v1/auth/me", headers=cab).json()
        assert eu["abas"] == ["/historico", "/audit"] and "audit.read" in eu["rbac_permissions"]
        assert cliente.get("/api/v1/governance/auditoria/eventos", headers=cab).status_code == 200
        # Quem não é admin não muda papéis (nem vê, sem admin.roles).
        assert cliente.post("/api/v1/papeis", json={"nome": "Outro"}, headers=cab).status_code == 403
        assert cliente.get("/api/v1/papeis", headers=cab).status_code == 403

    with com_login(cliente, admin) as cab:
        assert cliente.put(f"/api/v1/papeis/{papel['id']}", json={"abas": ["/historico"]}, headers=cab).status_code == 200
    with com_login(cliente, pessoa) as cab:
        eu = cliente.get("/api/v1/auth/me", headers=cab).json()
        assert eu["abas"] == ["/historico"] and "audit.read" not in eu["rbac_permissions"]
        assert cliente.get("/api/v1/governance/auditoria/eventos", headers=cab).status_code == 403  # perdeu o acesso
    with com_login(cliente, admin) as cab:
        cliente.put(f"/api/v1/papeis/{papel['id']}", json={"abas": ["/historico", "/audit"]}, headers=cab)
    with com_login(cliente, pessoa) as cab:
        assert cliente.get("/api/v1/governance/auditoria/eventos", headers=cab).status_code == 200  # ligar devolve

    with com_login(cliente, admin) as cab:
        lista = cliente.get("/api/v1/papeis", headers=cab).json()
        assert lista["pode_editar"] is True
        por_slug = {p["slug"]: p for p in lista["papeis"]}
        assert por_slug["admin"]["pode_mudar_abas"] is False and por_slug["admin"]["pode_apagar"] is False
        assert por_slug[papel["slug"]]["pessoas"] == 1
        admin_id, viewer_id = por_slug["admin"]["id"], por_slug["viewer"]["id"]
        assert cliente.put(f"/api/v1/papeis/{admin_id}", json={"abas": []}, headers=cab).status_code == 422
        assert cliente.delete(f"/api/v1/papeis/{viewer_id}", headers=cab).status_code == 422  # do sistema
        sem_destino = cliente.delete(f"/api/v1/papeis/{papel['id']}", headers=cab)
        assert sem_destino.status_code == 422 and "escolha para qual papel" in sem_destino.text
        apagado = cliente.delete(f"/api/v1/papeis/{papel['id']}", params={"substituto": viewer_id}, headers=cab)
        assert apagado.status_code == 200 and apagado.json()["pessoas_movidas"] == 1
        assert cliente.delete(f"/api/v1/papeis/{papel['id']}", headers=cab).status_code == 404
    sessao.expire_all()
    novo = sessao.execute(text("SELECT r.slug FROM users u JOIN roles r ON r.id = u.role_id WHERE u.email = :e"),
                          {"e": pessoa}).scalar_one()
    assert novo == "viewer"
    acoes = sessao.execute(text("SELECT action FROM audit_events WHERE resource_type = 'role' AND resource_id = :r "
                                "ORDER BY occurred_at"), {"r": str(papel["id"])}).scalars().all()
    assert acoes == ["papel.criado", "papel.alterado", "papel.alterado", "papel.apagado"]
    print("\npapéis: admin cria com abas (ganha a leitura), desligar Auditoria tira o acesso na API, ligar devolve; "
          "admin e do sistema protegidos; apagar move as pessoas para o substituto")


def test_criar_baseado_em_outro_copia_permissoes_e_abas(cliente, sessao) -> None:
    _garantir_permissoes(sessao)
    _, admin = _admin_com_senha(sessao)
    with com_login(cliente, admin) as cab:
        viewer = next(p for p in cliente.get("/api/v1/papeis", headers=cab).json()["papeis"] if p["slug"] == "viewer")
        copia = cliente.post("/api/v1/papeis", json={"nome": "Viewer da Folha", "baseado_em": viewer["id"]}, headers=cab).json()
        assert copia["abas"] == viewer["abas"]
        base = set(sessao.execute(text("SELECT permission_key FROM role_permissions WHERE role_id = :r"), {"r": viewer["id"]}).scalars())
        nova = set(sessao.execute(text("SELECT permission_key FROM role_permissions WHERE role_id = :r"), {"r": copia["id"]}).scalars())
        assert base <= nova
        adm = next(p for p in cliente.get("/api/v1/papeis", headers=cab).json()["papeis"] if p["slug"] == "admin")
        assert cliente.post("/api/v1/papeis", json={"nome": "Outro admin", "baseado_em": adm["id"]}, headers=cab).status_code == 422
        # nome repetido é recusado; o slug repetido (nome parecido) ganha um sufixo
        repetido = cliente.post("/api/v1/papeis", json={"nome": "viewer da folha"}, headers=cab)
        assert repetido.status_code == 422 and "Já existe" in repetido.text
        parecido = cliente.post("/api/v1/papeis", json={"nome": "Viewer da Folha!"}, headers=cab).json()
        assert parecido["slug"] == "viewer-da-folha-2" and parecido["abas"] == []
