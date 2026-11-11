"""Times: permissões por categoria (validação) e a soma com as da pessoa."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.access.application.use_cases import _legacy_category_allowed
from modules.access.domain.times import PermissaoDoTime, TimeInvalido, efetivas, validar_categorias, validar_membros


def test_categorias_validas_executar_implica_ver_e_vazia_sai() -> None:
    saida = validar_categorias([
        {"category_id": 3, "can_view": True},
        {"category_id": 5, "can_execute": True},
        {"category_id": 7, "can_view": False, "can_execute": False},
    ])
    assert saida == [PermissaoDoTime(3, True, False), PermissaoDoTime(5, True, True)]
    assert validar_categorias([]) == []


@pytest.mark.parametrize("bruto,trecho", [
    ("x", "envie uma lista"),
    (["x"], "categorias[0]: envie um objeto"),
    ([{"category_id": "3"}], "categorias[0].category_id"),
    ([{"category_id": True}], "categorias[0].category_id"),
    ([{"category_id": 0}], "categorias[0].category_id"),
    ([{"category_id": 3}, {"category_id": 3}], "categorias[1]: categoria repetida"),
])
def test_categorias_invalidas(bruto, trecho) -> None:
    with pytest.raises(TimeInvalido, match=trecho.replace("[", r"\[").replace("]", r"\]")):
        validar_categorias(bruto)


def test_so_true_de_verdade_conta() -> None:
    assert validar_categorias([{"category_id": 3, "can_view": "sim", "can_execute": 1}]) == []


def test_membros() -> None:
    assert validar_membros([7, 3, 7]) == [3, 7]
    assert validar_membros([]) == []
    for ruim in ("x", [0], [True], ["3"], None):
        with pytest.raises(TimeInvalido, match="informe os usuários pelo número"):
            validar_membros(ruim)
    with pytest.raises(TimeInvalido, match="informe os times pelo número"):
        validar_membros(["a"], "times")


def test_efetivas_soma_sem_perder_as_proprias() -> None:
    propria = SimpleNamespace(category_id=3, can_view=True, can_execute=False, can_edit=True)
    do_time = PermissaoDoTime(3, True, True)
    assert efetivas([propria], [do_time]) == [propria, do_time]
    usuario = SimpleNamespace(category_permissions=[propria], team_category_permissions=[do_time])
    assert _legacy_category_allowed(usuario, 3, "execution.create")  # vem do time
    assert _legacy_category_allowed(usuario, 3, "automation.update")  # própria (editar) continua
    assert not _legacy_category_allowed(usuario, 4, "automation.read")
    sem_time = SimpleNamespace(category_permissions=[propria])
    assert not _legacy_category_allowed(sem_time, 3, "execution.create")
