"""Declaração da automação: o que ela manda ao conectar, validado e com os limites."""

from __future__ import annotations

import pytest

from modules.catalog.domain import declaracao as d
from modules.catalog.domain.declaracao import ItemDeclarado, validar_declaracao
from modules.catalog.domain.formulario import FormularioInvalido

COMPLETA = {
    "versao": " 0.2.0 ",
    "parametros": [{"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano", "obrigatorio": True}],
    "itens": {"nome": "Empresa", "chave": "codigo", "grupo": "matriz_codigo",
              "colunas": [{"chave": "caminho_saida", "rotulo": "Pasta", "tipo": "pasta"}]},
    "tabela": [{"chave": "5081", "rotulo": "Matriz", "atributos": {"caminho_saida": "F:\\x"}}],
}


def test_declaracao_completa() -> None:
    dec = validar_declaracao(COMPLETA)
    assert dec.versao == "0.2.0"
    assert [(c.chave, c.origem) for c in dec.parametros] == [("competencia", "automacao")]
    assert dec.item == ItemDeclarado("Empresa", "codigo", "matriz_codigo")
    assert [(c.chave, c.origem) for c in dec.colunas] == [("caminho_saida", "automacao")]
    assert dec.tabela == COMPLETA["tabela"] and dec.tabela is not COMPLETA["tabela"]


def test_declaracao_minima() -> None:
    dec = validar_declaracao({})
    assert (dec.versao, dec.parametros, dec.item, dec.colunas, dec.tabela) == (None, [], None, [], None)
    assert validar_declaracao({"itens": {"nome": "Nota", "chave": "numero"}}).item == ItemDeclarado("Nota", "numero", None)


@pytest.mark.parametrize("bruto,erro", [
    ("x", "declaracao"),
    ({"parametros": [{"chave": "A", "rotulo": "A"}]}, "parametros.campos[0].chave"),
    ({"itens": "x"}, "itens"),
    ({"itens": {"chave": "codigo"}}, "itens.nome"),
    ({"itens": {"nome": "Empresa", "chave": "Código"}}, "itens.chave"),
    ({"itens": {"nome": "Empresa"}}, "itens.chave"),
    ({"itens": {"nome": "E", "chave": "c", "colunas": [{"chave": "x"}]}}, "itens.colunas.campos[0].rotulo"),
    ({"tabela": []}, "tabela"),
    ({"itens": {"nome": "E", "chave": "c"}, "tabela": "x"}, "tabela"),
    ({"itens": {"nome": "E", "chave": "c"}, "tabela": [{}] * 5001}, "tabela"),
    ({"itens": {"nome": "E", "chave": "c"}, "tabela": ["x"]}, "tabela"),
])
def test_declaracao_invalida(bruto, erro) -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_declaracao(bruto)
    assert erro in exc.value.campos


def test_limites_e_textos() -> None:
    assert d.LIMITE_TABELA == 5000
    assert len(validar_declaracao({"itens": {"nome": "E", "chave": "c"}, "tabela": [{}] * 5000}).tabela) == 5000
    dec = validar_declaracao({"versao": "v" * 50, "itens": {"nome": "n" * 70, "chave": "c", "grupo": " "}})
    assert (len(dec.versao), len(dec.item.nome), dec.item.grupo) == (40, 60, None)


def test_tabela_com_erro_no_item_nao_repete_o_erro() -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_declaracao({"itens": {"nome": "E", "chave": "C"}, "tabela": [{}]})
    assert set(exc.value.campos) == {"itens.chave"}


def test_chave_e_grupo_inteiros_ou_recusados() -> None:
    sessenta = "c" * 60
    dec = validar_declaracao({"itens": {"nome": "E", "chave": f" {sessenta} ", "grupo": "g" * 60}})
    assert (dec.item.chave, dec.item.grupo) == (sessenta, "g" * 60)
    for campo in ("chave", "grupo"):
        with pytest.raises(FormularioInvalido) as exc:  # cortar trocaria por outra chave
            validar_declaracao({"itens": {"nome": "E", "chave": "c", campo: "c" * 61}})
        assert f"itens.{campo}" in exc.value.campos
    with pytest.raises(FormularioInvalido) as exc:
        validar_declaracao({"itens": {"nome": "E", "chave": "c", "grupo": "Matriz Código"}})
    assert set(exc.value.campos) == {"itens.grupo"}
    assert validar_declaracao({"itens": {"nome": "E", "chave": "c", "grupo": None}}).item.grupo is None


def test_item_declarado_e_imutavel() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        ItemDeclarado("E", "c").chave = "x"  # type: ignore[misc]
