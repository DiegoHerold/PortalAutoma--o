"""Cadastro de itens: validação pelo schema do manifesto, grupo de um nível e prévia."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.catalog.domain.itens import (
    Item,
    ItemInvalido,
    configuracao_de_trabalho,
    conferir_grupos,
    previa,
    validar,
)

SPEC = SimpleNamespace(
    attributes_schema={"type": "object", "properties": {
        "separar_por_custo": {"type": "boolean"}, "email": {"type": "string"}, "codigo": {"type": "string"}},
        "required": ["separar_por_custo"]},
    work_attributes=("separar_por_custo",))


def d(chave, rotulo="Empresa", grupo=None, **atributos) -> dict:
    return {"chave": chave, "rotulo": rotulo, "grupo": grupo, "atributos": {"separar_por_custo": False, **atributos}}


def test_item_valido_e_matriz_que_aponta_para_si_nao_tem_grupo() -> None:
    item = validar(SPEC, d("5081", "Matriz 5081", grupo="5081", email="a@b.c"))
    assert item == Item("5081", "Matriz 5081", None, {"separar_por_custo": False, "email": "a@b.c"}, True)
    assert validar(SPEC, {**d(5066), "ativo": False}).ativo is False  # chave numérica vira texto


@pytest.mark.parametrize("dados,campo", [
    ({"chave": "", "rotulo": "x", "atributos": {"separar_por_custo": True}}, "chave"),
    ({"chave": "a b", "rotulo": "x", "atributos": {"separar_por_custo": True}}, "chave"),
    ({"chave": "1", "rotulo": " ", "atributos": {"separar_por_custo": True}}, "rotulo"),
    ({"chave": "1", "rotulo": "x" * 256, "atributos": {"separar_por_custo": True}}, "rotulo"),
    ({"chave": "1", "rotulo": "x", "grupo": "a/b", "atributos": {"separar_por_custo": True}}, "grupo"),
    ({"chave": "1", "rotulo": "x", "atributos": {}}, "atributos"),
    ({"chave": "1", "rotulo": "x", "atributos": {"separar_por_custo": "sim"}}, "atributos.separar_por_custo"),
    ({"chave": "1", "rotulo": "x", "atributos": []}, "atributos"),
])
def test_item_invalido_diz_o_campo(dados: dict, campo: str) -> None:
    with pytest.raises(ItemInvalido) as erro:
        validar(SPEC, dados)
    assert campo in erro.value.campos


def test_sem_schema_aceita_atributos_livres() -> None:
    assert validar(None, {"chave": "x", "rotulo": "X", "atributos": {"qualquer": 1}}).atributos == {"qualquer": 1}


def test_grupo_de_um_nivel_so() -> None:
    itens = {"1": Item("1", "Matriz"), "2": Item("2", "Filial", "1"), "3": Item("3", "Neta", "2"), "4": Item("4", "Órfã", "9")}
    assert conferir_grupos(itens) == {"3": "2 já é filial de 1: o grupo tem um nível só",
                                      "4": "o grupo 9 não está no cadastro"}


def test_configuracao_de_trabalho_leva_so_o_que_muda_o_trabalho() -> None:
    assert configuracao_de_trabalho(SPEC, {"separar_por_custo": True, "email": "x@y.z"}) == {"separar_por_custo": True}
    assert configuracao_de_trabalho(None, {"separar_por_custo": True}) == {}


def test_previa_separa_novos_alterados_iguais_e_erros() -> None:
    atuais = {"5081": Item("5081", "Matriz", None, {"separar_por_custo": False}),
              "5076": Item("5076", "Filial", "5081", {"separar_por_custo": False})}
    vindos = [
        d("5081", "Matriz"),                                  # igual
        d("5076", "Filial nova", grupo="5081", email="x"),    # alterada
        d("5075", "Outra filial", grupo="5081"),              # nova
        d("5075", "Repetida"),                                # repetida no arquivo
        d("6000", "Neta", grupo="5076"),                      # grupo de dois níveis
        {"chave": "", "rotulo": "sem chave"},                 # inválida
    ]
    r = previa(atuais, vindos, SPEC)
    assert r["iguais"] == 1
    assert [n["chave"] for n in r["novos"]] == ["5075"]
    assert r["alterados"] == [{"chave": "5076", "rotulo": "Filial nova", "grupo": "5081",
                               "atributos": {"separar_por_custo": False, "email": "x"}, "ativo": True,
                               "mudancas": ["rotulo", "atributos.email"]}]
    assert sorted((e["chave"], list(e["campos"])) for e in r["erros"]) == [
        ("", ["chave", "atributos"]), ("5075", ["chave"]), ("6000", ["grupo"])]


def test_limites_e_textos_vindos_de_fora() -> None:
    assert validar(SPEC, d("1", "x" * 255)).rotulo == "x" * 255
    mesma = "".join(list("5081"))
    assert validar(SPEC, d("5081", grupo=mesma)).grupo is None
    spec_curto = SimpleNamespace(attributes_schema={"type": "object", "properties": {"abc": {"type": "integer"}}}, work_attributes=())
    with pytest.raises(ItemInvalido) as erro:
        validar(spec_curto, {"chave": "1", "rotulo": "x", "atributos": {"abc": "texto"}})
    assert list(erro.value.campos) == ["atributos.abc"]


def test_item_e_imutavel() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        Item("1", "x").rotulo = "y"  # type: ignore[misc]


def test_previa_segue_depois_de_um_erro_e_conta_a_linha() -> None:
    vindos = [{"chave": "a b", "rotulo": "x", "atributos": {"separar_por_custo": True}}, d("1"), d("1"), d("2")]
    r = previa({}, vindos, SPEC)
    assert [n["chave"] for n in r["novos"]] == ["1", "2"]
    assert [(e["linha"], e["chave"]) for e in r["erros"]] == [(1, "a b"), (3, "1")]


def test_previa_mostra_item_desligado_e_atributo_trocado() -> None:
    atuais = {"1": Item("1", "Z", None, {"separar_por_custo": True, "lista": [1]})}
    r = previa(atuais, [{**d("1", "A"), "ativo": False, "atributos": {"separar_por_custo": True, "lista": [1]}}], SPEC)
    assert r["alterados"][0]["mudancas"] == ["rotulo", "ativo"]
    r = previa(atuais, [{**d("1", "Z"), "atributos": {"separar_por_custo": True, "lista": [2]}}], SPEC)
    assert r["alterados"][0]["mudancas"] == ["atributos.lista"]
    igual = previa(atuais, [{**d("1", "Z"), "atributos": {"separar_por_custo": True, "lista": [1]}}], SPEC)
    assert igual["iguais"] == 1


def test_erro_de_grupo_no_meio_nao_esconde_os_seguintes_e_nome_igual_nao_e_mudanca() -> None:
    r = previa({}, [d("9", grupo="8"), d("10")], SPEC)  # 9 aponta para grupo inexistente, 10 vem depois
    assert [n["chave"] for n in r["novos"]] == ["10"] and [e["chave"] for e in r["erros"]] == ["9"]
    nome = "".join(list("Empresa de nome longo"))  # mesmo texto, outro objeto (como vem do arquivo)
    atuais = {"1": Item("1", "Empresa de nome longo", None, {"separar_por_custo": False})}
    r = previa(atuais, [{**d("1", nome), "atributos": {"separar_por_custo": True}}], SPEC)
    assert r["alterados"][0]["mudancas"] == ["atributos.separar_por_custo"]
