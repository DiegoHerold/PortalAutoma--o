"""Papéis globais com funcionalidades (12/11/2026): só o admin cria, muda a tabela e apaga; cada
funcionalidade em "ver" ou "gerenciar" libera a área na tela e na API. Login de verdade (token)."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from tests.db.test_auditoria_completa import _admin_com_senha
from tests.db.test_times_e_maquinas import _pessoa, com_login


def _com_papel(sessao, papel_id: int) -> tuple[int, str]:
    uid, email = _pessoa(sessao)
    sessao.execute(text("UPDATE users SET role_id = :r WHERE id = :u"), {"r": papel_id, "u": uid})
    sessao.commit()
    return uid, email


def _papeis(cliente, cab) -> dict[str, dict]:
    return {p["slug"]: p for p in cliente.get("/api/v1/papeis", headers=cab).json()["papeis"]}


def test_tabela_de_funcionalidades_libera_e_tira_o_acesso(cliente, sessao) -> None:
    _, admin = _admin_com_senha(sessao)
    nome = f"Analista Fiscal {uuid.uuid4().hex[:4]}"
    with com_login(cliente, admin) as cab:
        catalogo = cliente.get("/api/v1/papeis/funcionalidades", headers=cab).json()["funcionalidades"]
        assert len(catalogo) == 22
        assert next(f for f in catalogo if f["chave"] == "usuarios")["niveis"] == ["ver", "gerenciar"]
        criado = cliente.post("/api/v1/papeis", json={"nome": nome, "descricao": "Confere a folha",
                                                      "funcionalidades": {"auditoria": "ver", "historico": "ver"}}, headers=cab)
        assert criado.status_code == 201, criado.text
        papel = criado.json()
        assert papel["funcionalidades"] == {"historico": "ver", "auditoria": "ver"}  # na ordem do menu
        assert papel["slug"].startswith("analista-fiscal") and papel["pode_apagar"] and papel["editavel"]
        assert cliente.post("/api/v1/papeis", json={"nome": "X1", "funcionalidades": {"auditoria": "gerenciar"}},
                            headers=cab).status_code == 422  # auditoria só se vê
        assert cliente.post("/api/v1/papeis", json={"nome": "X2", "funcionalidades": {"inventada": "ver"}},
                            headers=cab).status_code == 422
        viewer_id = _papeis(cliente, cab)["viewer"]["id"]

    _, pessoa = _com_papel(sessao, papel["id"])
    with com_login(cliente, pessoa) as cab:
        eu = cliente.get("/api/v1/auth/me", headers=cab).json()
        assert {"historico.ver", "auditoria.ver", "audit.read"} <= set(eu["rbac_permissions"])
        assert "painel.ver" not in eu["rbac_permissions"]  # a tabela manda: Painel não foi ligado
        assert cliente.get("/api/v1/governance/auditoria/eventos", headers=cab).status_code == 200
        assert cliente.get("/api/v1/historico", headers=cab).status_code == 200
        assert cliente.get("/api/v1/fila", headers=cab).status_code == 403
        assert cliente.get("/api/v1/painel", headers=cab).status_code == 403
        assert cliente.get("/api/v1/users", headers=cab).status_code == 403
        assert cliente.post("/api/v1/papeis", json={"nome": "Outro"}, headers=cab).status_code == 403
        assert cliente.get("/api/v1/papeis", headers=cab).status_code == 403

    with com_login(cliente, admin) as cab:
        mudar = cliente.put(f"/api/v1/papeis/{papel['id']}", json={"funcionalidades": {"historico": "ver", "usuarios": "ver"}},
                            headers=cab)
        assert mudar.status_code == 200, mudar.text
    with com_login(cliente, pessoa) as cab:
        assert cliente.get("/api/v1/governance/auditoria/eventos", headers=cab).status_code == 403  # tirou
        assert cliente.get("/api/v1/users", headers=cab).status_code == 200  # ver usuários
        novo = {"name": "Teste Papel", "email": f"p{uuid.uuid4().hex[:6]}@teste.invalid", "password": "Senha-Forte-123",
                "role_id": viewer_id}
        assert cliente.post("/api/v1/users", json=novo, headers=cab).status_code == 403  # gerenciar não

    with com_login(cliente, admin) as cab:
        papeis = _papeis(cliente, cab)
        assert papeis["admin"]["editavel"] is False and papeis["admin"]["pode_apagar"] is False
        assert len(papeis["admin"]["funcionalidades"]) == 22
        assert papeis[papel["slug"]]["pessoas"] == 1
        assert cliente.put(f"/api/v1/papeis/{papeis['admin']['id']}", json={"funcionalidades": {}}, headers=cab).status_code == 422
        assert cliente.delete(f"/api/v1/papeis/{viewer_id}", headers=cab).status_code == 422  # do sistema
        sem_destino = cliente.delete(f"/api/v1/papeis/{papel['id']}", headers=cab)
        assert sem_destino.status_code == 422 and "escolha para qual papel" in sem_destino.text
        apagado = cliente.delete(f"/api/v1/papeis/{papel['id']}", params={"substituto": viewer_id}, headers=cab)
        assert apagado.status_code == 200 and apagado.json()["pessoas_movidas"] == 1
    sessao.expire_all()
    assert sessao.execute(text("SELECT r.slug FROM users u JOIN roles r ON r.id = u.role_id WHERE u.email = :e"),
                          {"e": pessoa}).scalar_one() == "viewer"
    acoes = sessao.execute(text("SELECT action FROM audit_events WHERE resource_type = 'role' AND resource_id = :r "
                                "ORDER BY occurred_at"), {"r": str(papel["id"])}).scalars().all()
    assert acoes == ["papel.criado", "papel.alterado", "papel.apagado"]
    print("\npapéis: a tabela libera Histórico e Auditoria; tirar a Auditoria fecha a API; Usuários em 'ver' lista mas "
          "não cria; admin e do sistema protegidos; apagar move as pessoas")


def test_papeis_de_antes_continuam_como_estavam(cliente, sessao) -> None:
    """Sem tabela salva, o Manager segue gerenciando pessoas, times e organizações (antes era pelo nome)."""
    _, admin = _admin_com_senha(sessao)
    with com_login(cliente, admin) as cab:
        manager = _papeis(cliente, cab)["manager"]
        assert manager["funcionalidades"]["usuarios"] == "gerenciar" and manager["funcionalidades"]["times"] == "gerenciar"
    _, gestor = _com_papel(sessao, manager["id"])
    with com_login(cliente, gestor) as cab:
        assert cliente.get("/api/v1/users", headers=cab).status_code == 200
        assert cliente.get("/api/v1/teams", headers=cab).status_code == 200
        assert cliente.get("/api/v1/painel", headers=cab).status_code == 200


def test_criar_baseado_em_outro_copia_a_tabela(cliente, sessao) -> None:
    _, admin = _admin_com_senha(sessao)
    with com_login(cliente, admin) as cab:
        papeis = _papeis(cliente, cab)
        copia = cliente.post("/api/v1/papeis", json={"nome": f"Viewer da Folha {uuid.uuid4().hex[:4]}",
                                                     "baseado_em": papeis["viewer"]["id"]}, headers=cab).json()
        assert copia["funcionalidades"] == papeis["viewer"]["funcionalidades"]
        assert cliente.post("/api/v1/papeis", json={"nome": "Outro admin", "baseado_em": papeis["admin"]["id"]},
                            headers=cab).status_code == 422
        repetido = cliente.post("/api/v1/papeis", json={"nome": copia["nome"].lower()}, headers=cab)
        assert repetido.status_code == 422 and "Já existe" in repetido.text
        sem_base = cliente.post("/api/v1/papeis", json={"nome": f"Novo {uuid.uuid4().hex[:4]}"}, headers=cab).json()
        assert sem_base["funcionalidades"] == {"painel": "ver"}  # papel novo começa só com o Painel


def test_inicializacao_nao_quebra_com_papel_ajustado(sessao) -> None:
    """Regressão (12/11/2026): com abas ou funcionalidades desligadas num papel do sistema, a
    inicialização achava que faltavam permissões (olhava o que VALE, não o que está gravado) e
    tentava gravá-las de novo: chave única violada e a API não subia."""
    from bootstrap.defaults import BootstrapService

    BootstrapService(sessao).ensure_defaults()  # os papéis do sistema existem, com as permissões gravadas
    sessao.execute(text("""UPDATE roles SET abas = '["/fila", "/historico"]'::jsonb WHERE slug = 'manager'"""))
    sessao.execute(text("""UPDATE roles SET funcionalidades = '{"painel": "ver"}'::jsonb WHERE slug = 'operator'"""))
    sessao.commit()
    try:
        BootstrapService(sessao).ensure_defaults()
        BootstrapService(sessao).ensure_defaults()  # e de novo, como a cada start
        gravadas = sessao.execute(text("SELECT permission_key FROM role_permissions rp JOIN roles r ON r.id = rp.role_id "
                                       "WHERE r.slug = 'manager'")).scalars().all()
        assert "audit.read" in gravadas and len(gravadas) == len(set(gravadas))  # gravada uma vez, filtrada no que vale
        assert sessao.execute(text("SELECT abas FROM roles WHERE slug = 'manager'")).scalar() == ["/fila", "/historico"]
    finally:
        sessao.execute(text("UPDATE roles SET abas = NULL WHERE slug = 'manager'"))
        sessao.execute(text("UPDATE roles SET funcionalidades = NULL WHERE slug = 'operator'"))
        sessao.commit()
