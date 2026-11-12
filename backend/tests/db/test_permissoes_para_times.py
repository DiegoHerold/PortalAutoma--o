"""Etapa 2 (12/11/2026): as permissões por categoria saem da pessoa e vão para times, sem ninguém
ganhar ou perder acesso."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.repositories.migracao_para_times import migrar
from modules.access.application.use_cases import _legacy_category_allowed
from tests.db.test_fase6_notificacoes_retencao import _usuario


def _categoria(sessao) -> int:
    nome = f"Cat {uuid.uuid4().hex[:6]}"
    return sessao.execute(text("INSERT INTO categories (name, slug, description, is_active) VALUES (:n, :s, :d, true) "
                               "RETURNING id"), {"n": nome, "s": nome.lower().replace(" ", "-"), "d": nome}).scalar_one()


def _dar(sessao, user_id: int, categoria: int, **marcas: bool) -> None:
    colunas = ["can_view", "can_execute", "can_create", "can_edit", "can_delete", "can_approve"]
    sessao.execute(text("INSERT INTO user_category_permissions (user_id, category_id, " + ", ".join(colunas) + ") VALUES "
                        "(:u, :c, " + ", ".join(f":{c}" for c in colunas) + ")"),
                   {"u": user_id, "c": categoria, **{c: marcas.get(c, False) for c in colunas}})


def _pode(sessao, user_id: int, permissao: str, categoria: int) -> bool:
    access = build_access_adapters(sessao).access
    usuario = access.get_user_record(user_id)
    usuario.team_category_permissions = access.categorias_pelos_times(user_id)
    return _legacy_category_allowed(usuario, categoria, permissao)


def test_permissoes_soltas_viram_times_sem_mudar_o_acesso(sessao) -> None:
    folha, fiscal = _categoria(sessao), _categoria(sessao)
    ana, _ = _usuario(sessao, "operator")
    bia, _ = _usuario(sessao, "operator")
    caio, _ = _usuario(sessao, "operator")
    chefe, _ = _usuario(sessao, "admin")
    for pessoa in (ana, bia):  # mesmo conjunto: um time só
        _dar(sessao, pessoa, folha, can_view=True, can_execute=True, can_edit=True, can_approve=True)
        _dar(sessao, pessoa, fiscal, can_view=True)
    _dar(sessao, caio, fiscal, can_view=True, can_execute=True)
    _dar(sessao, chefe, folha, can_view=True, can_execute=True, can_create=True, can_edit=True, can_delete=True, can_approve=True)
    sessao.commit()
    antes = {(p, perm, c): _pode(sessao, p, perm, c) for p in (ana, bia, caio)
             for perm in ("automation.read", "execution.create", "automation.update", "automation.publish", "automation.create")
             for c in (folha, fiscal)}

    resultado = migrar(sessao.connection())
    sessao.commit()
    assert resultado["times"] >= 2 and resultado["pessoas"] >= 3
    assert sessao.execute(text("SELECT count(*) FROM user_category_permissions WHERE user_id IN (:a, :b, :c, :d)"),
                          {"a": ana, "b": bia, "c": caio, "d": chefe}).scalar_one() == 0  # nada solto na pessoa

    times_da_ana = sessao.execute(text("SELECT team_id FROM access_team_memberships WHERE user_id = :u"), {"u": ana}).scalars().all()
    times_da_bia = sessao.execute(text("SELECT team_id FROM access_team_memberships WHERE user_id = :u"), {"u": bia}).scalars().all()
    assert len(times_da_ana) == 1 and times_da_ana == times_da_bia  # mesmo conjunto, mesmo time
    nome = sessao.execute(text("SELECT name FROM access_teams WHERE id = :t"), {"t": times_da_ana[0]}).scalar_one()
    assert nome.startswith("Acessos de ") and " e " in nome
    marcas = sessao.execute(text("SELECT can_view, can_execute, can_create, can_edit, can_delete, can_approve FROM "
                                 "access_team_category_permissions WHERE team_id = :t AND category_id = :c"),
                            {"t": times_da_ana[0], "c": folha}).one()
    assert tuple(marcas) == (True, True, False, True, False, True)  # exatamente o que a pessoa tinha
    assert not sessao.execute(text("SELECT count(*) FROM access_team_memberships WHERE user_id = :u"), {"u": chefe}).scalar_one()

    depois = {(p, perm, c): _pode(sessao, p, perm, c) for (p, perm, c) in antes}
    assert depois == antes  # ninguém ganhou nem perdeu
    assert migrar(sessao.connection())["times"] == 0  # rodar de novo não faz nada
    print(f"\netapa 2: {resultado} — Ana e Bia no mesmo time, Caio no dele, admin só perdeu o que não usava; acesso idêntico")


def test_time_guarda_editar_e_publicar(cliente, sessao) -> None:
    categoria = _categoria(sessao)
    org = sessao.execute(text("SELECT id FROM access_organizations ORDER BY id LIMIT 1")).scalar()
    if org is None:
        org = sessao.execute(text("INSERT INTO access_organizations (key, name, status) VALUES ('default', 'Padrão', 'active') "
                                  "RETURNING id")).scalar_one()
    sessao.commit()
    time = cliente.post("/api/v1/teams", json={"organization_id": org, "key": f"t-{uuid.uuid4().hex[:6]}", "name": "Fiscal"}).json()
    resposta = cliente.put(f"/api/v1/teams/{time['id']}/categorias",
                           json={"categorias": [{"category_id": categoria, "can_edit": True, "can_approve": True}]})
    assert resposta.status_code == 200, resposta.text
    linha = resposta.json()["categorias"][0]
    # editar vale pelas três de cadastro, e quem edita também vê
    assert (linha["can_view"], linha["can_create"], linha["can_edit"], linha["can_delete"], linha["can_approve"]) == (True,) * 5
    assert linha["can_execute"] is False
