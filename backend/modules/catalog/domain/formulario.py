"""Campos de uma automação (Fase 7): o que se informa ao pedir e o que se guarda em cada item.

Cada automação tem entradas diferentes. O Portal guarda e edita livremente (decisão de
11/11/2026): o manifesto só sugere os campos iniciais. Dois conjuntos:

- ``entrada``: o que se informa ao acionar (ex.: competência, modo);
- ``colunas``: o que cada item guarda (ex.: da empresa, pasta de destino e e-mail).

Aqui ficam as regras: campo válido, valor convertido para o tipo do campo (aceita a forma
brasileira, como ``1,5`` e ``31/10/2026``), padrão aplicado e obrigatório conferido. Campo
criado no Portal chega à automação no pedido; ela só faz algo com ele se o código ler.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TIPOS = ("texto", "texto_longo", "numero", "inteiro", "sim_nao", "data", "mes_ano", "lista", "email", "pasta", "json")
FORMATO_CHAVE = re.compile(r"[a-z][a-z0-9_]{0,59}")
LIMITE_CAMPOS = 60
LIMITE_OPCOES = 100
LIMITE_TEXTO = 2000
LIMITE_TEXTO_LONGO = 20000
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
SIM = ("sim", "s", "true", "1", "yes", "verdadeiro")
NAO = ("nao", "não", "n", "false", "0", "no", "falso")


class FormularioInvalido(ValueError):
    def __init__(self, campos: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in campos.items()))
        self.campos = campos


@dataclass(frozen=True)
class Campo:
    chave: str
    rotulo: str
    tipo: str = "texto"
    obrigatorio: bool = False
    padrao: Any = None
    opcoes: tuple[str, ...] = ()
    ajuda: str | None = None
    afeta_trabalho: bool = False  # coluna de item que muda o tempo do trabalho (estimativa)

    def publico(self) -> dict[str, Any]:
        return {"chave": self.chave, "rotulo": self.rotulo, "tipo": self.tipo, "obrigatorio": self.obrigatorio,
                "padrao": self.padrao, "opcoes": list(self.opcoes), "ajuda": self.ajuda,
                "afeta_trabalho": self.afeta_trabalho}


def _vazio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def converter(campo: Campo, valor: Any) -> Any:
    """Valor no tipo do campo. ``ValueError`` com a mensagem para a pessoa."""
    tipo = campo.tipo
    if tipo in ("texto", "texto_longo", "pasta"):
        texto = str(valor).strip()
        limite = LIMITE_TEXTO_LONGO if tipo == "texto_longo" else LIMITE_TEXTO
        if len(texto) > limite:
            raise ValueError(f"até {limite} caracteres")
        return texto
    if tipo == "email":
        texto = str(valor).strip()
        if not EMAIL.fullmatch(texto):
            raise ValueError("e-mail inválido")
        return texto
    if tipo == "inteiro":
        if isinstance(valor, bool):
            raise ValueError("use um número inteiro")
        try:
            return int(str(valor).strip())
        except ValueError:
            raise ValueError("use um número inteiro") from None
    if tipo == "numero":
        if isinstance(valor, bool):
            raise ValueError("use um número")
        if isinstance(valor, (int, float)):
            return valor
        texto = str(valor).strip().replace(" ", "")
        if "," in texto:  # forma brasileira: 1.234,5
            texto = texto.replace(".", "").replace(",", ".")
        try:
            return float(texto)
        except ValueError:
            raise ValueError("use um número") from None
    if tipo == "sim_nao":
        if isinstance(valor, bool):
            return valor
        texto = str(valor).strip().lower()
        if texto in SIM:
            return True
        if texto in NAO:
            return False
        raise ValueError("use sim ou não")
    if tipo == "data":
        texto = str(valor).strip()
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", texto)
        try:
            dia = date(int(m[3]), int(m[2]), int(m[1])) if m else date.fromisoformat(texto)
        except ValueError:
            raise ValueError("data inválida (use dd/mm/aaaa)") from None
        return dia.isoformat()
    if tipo == "mes_ano":
        texto = str(valor).strip()
        m = (re.fullmatch(r"(\d{1,2})/(\d{4})", texto) or re.fullmatch(r"(\d{2})(\d{4})", texto))
        if m:
            mes, ano = int(m[1]), int(m[2])
        else:
            m = re.fullmatch(r"(\d{4})-(\d{2})", texto)
            if not m:
                raise ValueError("use MM/AAAA")
            ano, mes = int(m[1]), int(m[2])
        if not 1 <= mes <= 12 or not 1900 <= ano <= 2999:
            raise ValueError("use MM/AAAA")
        return f"{mes:02d}/{ano}"
    if tipo == "lista":
        texto = str(valor).strip()
        if texto not in campo.opcoes:
            raise ValueError(f"escolha uma das opções: {', '.join(campo.opcoes)}")
        return texto
    if tipo == "json":
        return valor
    raise ValueError(f"tipo desconhecido: {tipo}")


def _campo(bruto: Any, posicao: int, erros: dict[str, str]) -> Campo | None:
    onde = f"campos[{posicao}]"
    if not isinstance(bruto, dict):
        erros[onde] = "cada campo é um objeto"
        return None
    chave = str(bruto.get("chave") or "").strip()
    rotulo = str(bruto.get("rotulo") or "").strip()
    tipo = str(bruto.get("tipo") or "texto").strip()
    falhou = False
    if not FORMATO_CHAVE.fullmatch(chave):
        erros[f"{onde}.chave"] = "letras minúsculas, números e _ (começa com letra, até 60)"
        falhou = True
    if not rotulo or len(rotulo) > 120:
        erros[f"{onde}.rotulo"] = "informe o nome (até 120 caracteres)"
        falhou = True
    if tipo not in TIPOS:
        erros[f"{onde}.tipo"] = f"tipo desconhecido: {tipo}"
        return None
    opcoes: tuple[str, ...] = ()
    if tipo == "lista":
        brutas = bruto.get("opcoes") or []
        opcoes = tuple(dict.fromkeys(str(o).strip() for o in brutas if not _vazio(o))) if isinstance(brutas, list) else ()
        if not 1 <= len(opcoes) <= LIMITE_OPCOES:
            erros[f"{onde}.opcoes"] = f"uma lista precisa de 1 a {LIMITE_OPCOES} opções"
            falhou = True
    ajuda = bruto.get("ajuda")
    ajuda = str(ajuda).strip()[:300] if not _vazio(ajuda) else None
    if falhou:
        return None
    campo = Campo(chave, rotulo, tipo, bool(bruto.get("obrigatorio")), None, opcoes, ajuda,
                  bool(bruto.get("afeta_trabalho")))
    padrao = bruto.get("padrao")
    if not _vazio(padrao):
        try:
            padrao = converter(campo, padrao)
        except ValueError as exc:
            erros[f"{onde}.padrao"] = str(exc)
            return None
        campo = Campo(chave, rotulo, tipo, campo.obrigatorio, padrao, opcoes, ajuda, campo.afeta_trabalho)
    return campo


def validar_campos(brutos: Any) -> list[Campo]:
    """Campos prontos para guardar, na ordem recebida."""
    if not isinstance(brutos, list):
        raise FormularioInvalido({"campos": "envie uma lista de campos"})
    if len(brutos) > LIMITE_CAMPOS:
        raise FormularioInvalido({"campos": f"até {LIMITE_CAMPOS} campos"})
    erros: dict[str, str] = {}
    campos: list[Campo] = []
    vistos: set[str] = set()
    for posicao, bruto in enumerate(brutos):
        campo = _campo(bruto, posicao, erros)
        if campo is None:
            continue
        if campo.chave in vistos:
            erros[f"campos[{posicao}].chave"] = f"chave repetida: {campo.chave}"
            continue
        vistos.add(campo.chave)
        campos.append(campo)
    if erros:
        raise FormularioInvalido(erros)
    return campos


def valores(campos: Iterable[Campo], recebidos: Any, *, manter_extras: bool = False) -> dict[str, Any]:
    """Valores conferidos: padrão aplicado, obrigatório exigido, tipo convertido.

    ``manter_extras``: chaves que não são campos ficam como vieram (colunas de item apagadas
    no Portal não apagam o dado). Sem isso, chave desconhecida é erro (entrada do pedido)."""
    if recebidos is None:
        recebidos = {}
    if not isinstance(recebidos, dict):
        raise FormularioInvalido({"valores": "envie um objeto"})
    lista = list(campos)
    conhecidos = {c.chave for c in lista}
    erros: dict[str, str] = {}
    saida: dict[str, Any] = {}
    if manter_extras:
        saida.update({k: v for k, v in recebidos.items() if k not in conhecidos})
    else:
        for chave in recebidos:
            if chave not in conhecidos:
                erros[str(chave)] = "campo desconhecido nesta automação"
    for campo in lista:
        valor = recebidos.get(campo.chave)
        if _vazio(valor):
            valor = campo.padrao
        if _vazio(valor):
            if campo.obrigatorio:
                erros[campo.chave] = "obrigatório"
            continue
        try:
            saida[campo.chave] = converter(campo, valor)
        except ValueError as exc:
            erros[campo.chave] = str(exc)
    if erros:
        raise FormularioInvalido(erros)
    return saida


# -- ponte com JSON Schema (manifesto e validação dos itens) -----------------------------------

def de_esquema_json(esquema: Any, afetam_trabalho: Iterable[str] = ()) -> list[Campo]:
    """Campos sugeridos a partir do JSON Schema do manifesto (ponto de partida)."""
    if not isinstance(esquema, dict):
        return []
    propriedades = esquema.get("properties") if isinstance(esquema.get("properties"), dict) else {}
    obrigatorios = set(esquema.get("required") or [])
    trabalho = set(afetam_trabalho)
    campos = []
    for chave, prop in propriedades.items():
        if not isinstance(prop, dict) or not FORMATO_CHAVE.fullmatch(str(chave)):
            continue
        tipo_json, formato = prop.get("type"), prop.get("format")
        if prop.get("enum"):
            tipo = "lista"
        elif tipo_json == "boolean":
            tipo = "sim_nao"
        elif tipo_json == "integer":
            tipo = "inteiro"
        elif tipo_json == "number":
            tipo = "numero"
        elif tipo_json == "string":
            tipo = {"date": "data", "email": "email"}.get(formato, "texto")
        else:
            tipo = "json"
        campos.append(Campo(str(chave), str(prop.get("title") or chave), tipo, chave in obrigatorios,
                            prop.get("default"), tuple(str(o) for o in prop.get("enum") or ()),
                            prop.get("description"), chave in trabalho))
    return campos


def para_esquema_json(campos: Iterable[Campo]) -> dict[str, Any]:
    """JSON Schema equivalente, para a validação de itens que já existe (Fase 5)."""
    tipos = {"numero": {"type": "number"}, "inteiro": {"type": "integer"}, "sim_nao": {"type": "boolean"}, "json": {}}
    propriedades: dict[str, Any] = {}
    obrigatorios = []
    for c in campos:
        prop = dict(tipos.get(c.tipo, {"type": "string"}))
        if c.tipo == "lista":
            prop["enum"] = list(c.opcoes)
        prop["title"] = c.rotulo
        propriedades[c.chave] = prop
        if c.obrigatorio:
            obrigatorios.append(c.chave)
    esquema: dict[str, Any] = {"type": "object", "properties": propriedades}
    if obrigatorios:
        esquema["required"] = obrigatorios
    return esquema


def de_guardados(brutos: Any) -> list[Campo]:
    """Campos já guardados no banco (válidos quando gravados)."""
    return validar_campos(brutos or [])


@dataclass
class Formulario:
    entrada: list[Campo] = field(default_factory=list)
    colunas: list[Campo] = field(default_factory=list)
    origem: str = "manifesto"  # manifesto | portal
