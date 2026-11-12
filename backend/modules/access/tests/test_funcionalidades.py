"""Funcionalidades dos papéis: o catálogo com as 22 do menu, os níveis, o que cada nível dá e a
dedução dos papéis de antes (ninguém ganha nem perde acesso)."""

from __future__ import annotations

import pytest

from modules.access.domain.abas import slug_do_nome
from modules.access.domain.funcionalidades import (
    FUNCIONALIDADES,
    FuncionalidadeInvalida,
    catalogo,
    deduzir,
    permissoes_da_tabela,
    permissoes_efetivas,
    validar,
)

OPERADOR = ["automation.read", "execution.read", "execution.create", "execution.cancel", "flow.read", "flow.execute",
            "schedule.read", "schedule.trigger", "artifact.read", "artifact.download", "agent.read"]
VIEWER = ["automation.read", "execution.read", "flow.read", "schedule.read", "artifact.read", "agent.read"]


def test_catalogo_tem_as_22_do_menu_agrupadas() -> None:
    assert len(FUNCIONALIDADES) == 22 and len({f.chave for f in FUNCIONALIDADES}) == 22
    grupos = [f.grupo for f in FUNCIONALIDADES]
    assert list(dict.fromkeys(grupos)) == ["Monitorar", "Operação", "Catálogo", "Infraestrutura", "Segurança",
                                           "Pessoas e acesso", "Governança"]
    papeis = next(c for c in catalogo() if c["chave"] == "papeis")
    assert papeis["niveis"] == ["ver"]  # mudar papéis é só do Admin


def test_validar_ordena_ignora_desligadas_e_recusa_o_que_nao_existe() -> None:
    assert validar({"usuarios": "gerenciar", "painel": "ver", "fila": None, "historico": ""}) == {
        "painel": "ver", "usuarios": "gerenciar"}
    with pytest.raises(FuncionalidadeInvalida, match="desconhecida"):
        validar({"painel-secreto": "ver"})
    with pytest.raises(FuncionalidadeInvalida, match="não existe"):
        validar({"auditoria": "gerenciar"})  # auditoria só se vê


def test_cada_nivel_da_a_chave_propria_e_as_tecnicas_da_area() -> None:
    dadas = permissoes_da_tabela({"agendamentos": "gerenciar", "auditoria": "ver"})
    assert {"agendamentos.ver", "agendamentos.gerenciar", "schedule.read", "schedule.create", "auditoria.ver",
            "audit.read"} <= dadas
    assert "fila.ver" not in dadas
    so_ver = permissoes_da_tabela({"agendamentos": "ver"})
    assert "schedule.read" in so_ver and "schedule.create" not in so_ver and "agendamentos.gerenciar" not in so_ver


def test_papeis_de_antes_mantem_o_que_tinham() -> None:
    operador = deduzir("operator", OPERADOR)
    assert operador["painel"] == "ver" and operador["historico"] == "ver" and operador["fila"] == "gerenciar"
    assert operador["execucoes"] == "gerenciar" and "usuarios" not in operador and "auditoria" not in operador
    viewer = deduzir("viewer", VIEWER)
    assert viewer["execucoes"] == "ver" and viewer["fila"] == "ver" and "agendamentos" in viewer
    # O Manager tinha as áreas liberadas pelo nome do papel.
    gestor = deduzir("manager", ["automation.read", "automation.create", "execution.read"])
    assert gestor["usuarios"] == "gerenciar" and gestor["times"] == "gerenciar" and gestor["organizacoes"] == "gerenciar"
    assert gestor["categorias"] == "gerenciar" and gestor["maquinas"] == "gerenciar" and gestor["automacoes"] == "gerenciar"
    assert "limites" not in gestor  # era admin.system, que o Manager não tem
    # Efetivas: tudo o que estava gravado continua, mais as chaves das funcionalidades.
    efetivas = permissoes_efetivas("operator", OPERADOR, None, None)
    assert set(OPERADOR) <= set(efetivas) and {"historico.ver", "fila.gerenciar", "painel.ver"} <= set(efetivas)
    assert "usuarios.ver" not in efetivas


def test_tabela_salva_manda() -> None:
    efetivas = permissoes_efetivas("operator", OPERADOR, None, {"historico": "ver"})
    assert set(efetivas) == {"historico.ver"}  # tirou tudo o que não está na tabela


def test_abas_da_etapa_anterior_ainda_valem_no_papel_de_antes() -> None:
    gestor = deduzir("manager", ["audit.read", "execution.read"], abas=["/historico"])
    assert "auditoria" not in gestor and "fila" not in gestor and gestor["historico"] == "ver"
    assert "usuarios" not in gestor  # "/users" era aba configurável e ficou desligada
    assert gestor["times"] == "gerenciar"  # Times não era configurável: segue pelo nome do papel
    assert "audit.read" not in permissoes_efetivas("manager", ["audit.read"], ["/historico"], None)


def test_slug() -> None:
    assert slug_do_nome("  Analista Fiscal (Folha) ") == "analista-fiscal-folha"
    with pytest.raises(FuncionalidadeInvalida):
        slug_do_nome("!!!")
