"""Declaração da automação (Fase 8): o que ela manda ao se conectar ao Portal.

A cada conexão, a automação diz quais informações pede para executar (``parametros``), o que
é um item dela e quais colunas ele tem (``itens``) e, se tiver, a tabela de itens dela
(``tabela``, ex.: as empresas do ``empresas.db``). O Portal:

- junta os campos (só acrescenta: ver ``formulario.juntar``);
- guarda a tabela como uma **prévia** que alguém aprova na aba Itens (nada muda sozinho).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.catalog.domain.formulario import FORMATO_CHAVE, Campo, FormularioInvalido, da_automacao, validar_campos

LIMITE_TABELA = 5000


@dataclass(frozen=True)
class ItemDeclarado:
    nome: str
    chave: str
    grupo: str | None = None


@dataclass
class Declaracao:
    versao: str | None = None
    parametros: list[Campo] = field(default_factory=list)
    item: ItemDeclarado | None = None
    colunas: list[Campo] = field(default_factory=list)
    tabela: list[dict[str, Any]] | None = None


def _texto(valor: Any, limite: int) -> str | None:
    texto = str(valor).strip() if valor is not None else ""
    return texto[:limite] or None


def _chave(valor: Any) -> str | None:
    """Chave inteira ou nada: cortar trocaria a chave por outra (o formato já limita a 60)."""
    return (str(valor).strip() or None) if valor is not None else None


def validar_declaracao(bruto: Any) -> Declaracao:
    if not isinstance(bruto, dict):
        raise FormularioInvalido({"declaracao": "envie um objeto"})
    erros: dict[str, str] = {}
    parametros: list[Campo] = []
    try:
        parametros = da_automacao(validar_campos(bruto.get("parametros") or []))
    except FormularioInvalido as exc:
        erros.update({f"parametros.{k}": v for k, v in exc.campos.items()})
    item, colunas = None, []
    itens = bruto.get("itens")
    if itens is not None:
        if not isinstance(itens, dict):
            erros["itens"] = "envie um objeto com nome, chave e colunas"
        else:
            nome, chave, grupo = _texto(itens.get("nome"), 60), _chave(itens.get("chave")), _chave(itens.get("grupo"))
            if not nome:
                erros["itens.nome"] = "informe o nome do item (ex.: Empresa)"
            if not chave or not FORMATO_CHAVE.fullmatch(chave):
                erros["itens.chave"] = "chave do item: letras minúsculas, números e _ (até 60)"
            if grupo is not None and not FORMATO_CHAVE.fullmatch(grupo):
                erros["itens.grupo"] = "grupo do item: a chave de uma coluna (letras minúsculas, números e _, até 60)"
            try:
                colunas = da_automacao(validar_campos(itens.get("colunas") or []))
            except FormularioInvalido as exc:
                erros.update({f"itens.colunas.{k}": v for k, v in exc.campos.items()})
            if nome and chave:
                item = ItemDeclarado(nome, chave, grupo)
    tabela = bruto.get("tabela")
    if tabela is not None:
        if item is None and "itens" not in erros and not any(k.startswith("itens.") for k in erros):
            erros["tabela"] = "a tabela precisa da definição do item (itens)"
        elif not isinstance(tabela, list):
            erros["tabela"] = "envie uma lista de itens"
        elif len(tabela) > LIMITE_TABELA:
            erros["tabela"] = f"até {LIMITE_TABELA} itens"
        elif not all(isinstance(linha, dict) for linha in tabela):
            erros["tabela"] = "cada item é um objeto"
    if erros:
        raise FormularioInvalido(erros)
    return Declaracao(_texto(bruto.get("versao"), 40), parametros, item, colunas,
                      list(tabela) if isinstance(tabela, list) else None)
