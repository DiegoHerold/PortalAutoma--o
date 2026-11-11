"""Cadastro de itens por automação (decisão 1 da Fase 0; seção 6.5).

O manifesto declara o que é um item (``ItemSpec``): o nome na tela, a chave, o grupo e o
JSON Schema dos atributos. Aqui ficam as regras do cadastro: item válido pelo schema, grupo
de um nível só (matriz e filiais) e a prévia de uma importação antes de gravar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator

FORMATO_CHAVE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")
LIMITE_ROTULO = 255


class ItemInvalido(ValueError):
    def __init__(self, campos: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in campos.items()))
        self.campos = campos


@dataclass(frozen=True)
class Item:
    chave: str
    rotulo: str
    grupo: str | None = None
    atributos: dict[str, Any] = field(default_factory=dict)
    ativo: bool = True


def validar(spec: Any, dados: dict[str, Any]) -> Item:
    """Item pronto para gravar. ``spec`` é o ``ItemSpec`` do manifesto (ou None: sem schema)."""
    erros: dict[str, str] = {}
    chave = str(dados.get("chave") if dados.get("chave") is not None else "").strip()
    if not FORMATO_CHAVE.fullmatch(chave):
        erros["chave"] = "use letras, números, ponto, hífen ou sublinhado (até 120)"
    rotulo = str(dados.get("rotulo") or "").strip()
    if not rotulo:
        erros["rotulo"] = "informe o nome"
    elif len(rotulo) > LIMITE_ROTULO:
        erros["rotulo"] = f"até {LIMITE_ROTULO} caracteres"
    grupo_bruto = dados.get("grupo")
    grupo = str(grupo_bruto).strip() if grupo_bruto not in (None, "") else None
    if grupo is not None and grupo == chave:
        grupo = None  # a matriz é o grupo dela mesma: não aponta para si
    elif grupo is not None and not FORMATO_CHAVE.fullmatch(grupo):
        erros["grupo"] = "chave de grupo inválida"
    atributos = dados.get("atributos") or {}
    if not isinstance(atributos, dict):
        erros["atributos"] = "deve ser um objeto"
        atributos = {}
    schema = getattr(spec, "attributes_schema", None)
    if schema:
        for erro in sorted(Draft202012Validator(schema).iter_errors(atributos), key=lambda e: list(e.absolute_path)):
            caminho = ".".join(str(p) for p in erro.absolute_path) or "atributos"
            erros.setdefault(f"atributos.{caminho}" if caminho != "atributos" else caminho, erro.message)
    if erros:
        raise ItemInvalido(erros)
    return Item(chave, rotulo, grupo, dict(atributos), bool(dados.get("ativo", True)))


def conferir_grupos(itens: dict[str, Item]) -> dict[str, str]:
    """Grupo de um nível só: o grupo precisa existir e não pode ser filial de outro."""
    erros: dict[str, str] = {}
    for item in itens.values():
        if item.grupo is None:
            continue
        matriz = itens.get(item.grupo)
        if matriz is None:
            erros[item.chave] = f"o grupo {item.grupo} não está no cadastro"
        elif matriz.grupo is not None:
            erros[item.chave] = f"{item.grupo} já é filial de {matriz.grupo}: o grupo tem um nível só"
    return erros


def configuracao_de_trabalho(spec: Any, atributos: dict[str, Any]) -> dict[str, Any]:
    """Só os atributos que mudam o trabalho (regra 6 da estimativa); o resto não vai no pedido."""
    return {nome: atributos[nome] for nome in getattr(spec, "work_attributes", ()) if nome in atributos}


def previa(atuais: dict[str, Item], vindos: list[dict[str, Any]], spec: Any) -> dict[str, Any]:
    """O que a importação faria, sem gravar: novos, alterados (com as mudanças), iguais e erros."""
    novos, alterados, iguais, erros = [], [], 0, []
    validos: dict[str, Item] = {}
    for posicao, bruto in enumerate(vindos, 1):
        try:
            item = validar(spec, bruto)
        except ItemInvalido as exc:
            erros.append({"linha": posicao, "chave": str(bruto.get("chave") or ""), "campos": exc.campos})
            continue
        if item.chave in validos:
            erros.append({"linha": posicao, "chave": item.chave, "campos": {"chave": "repetida no arquivo"}})
            continue
        validos[item.chave] = item
    resultado = {**atuais, **validos}
    problemas_de_grupo = conferir_grupos(resultado)
    for chave, item in validos.items():
        if chave in problemas_de_grupo:
            erros.append({"linha": None, "chave": chave, "campos": {"grupo": problemas_de_grupo[chave]}})
            continue
        atual = atuais.get(chave)
        if atual is None:
            novos.append(_publico(item))
        elif atual == item:
            iguais += 1
        else:
            alterados.append({**_publico(item), "mudancas": _mudancas(atual, item)})
    return {"novos": novos, "alterados": alterados, "iguais": iguais, "erros": erros}


def _publico(item: Item) -> dict[str, Any]:
    return {"chave": item.chave, "rotulo": item.rotulo, "grupo": item.grupo, "atributos": item.atributos, "ativo": item.ativo}


def _mudancas(antes: Item, depois: Item) -> list[str]:
    saida = [campo for campo in ("rotulo", "grupo", "ativo") if getattr(antes, campo) != getattr(depois, campo)]
    nomes = sorted(set(antes.atributos) | set(depois.atributos))
    saida += [f"atributos.{n}" for n in nomes if antes.atributos.get(n) != depois.atributos.get(n)]
    return saida
