"""Segredos (0.5.0): senhas e chaves que a automação recebe do Portal durante a execução.

Um segredo é um objeto com campos (Domínio: ``usuario``, ``senha``, ``banco``)::

    dominio = a.segredo("dominio")          # Segredo: dominio["senha"], dominio.get("banco")
    senha = a.segredo("dominio", "senha")   # só um campo, em texto

- Modo direto: o SDK pede ao Portal com o token do job (``POST .../segredos``). Só sai o que
  está ligado à automação no Portal (aba Técnico), ativo e dentro da validade.
- Modo desligado (desenvolvimento): lê do ambiente. ``PORTAL_SEGREDO_<CHAVE>`` com um JSON
  (``{"usuario": "x", "senha": "y"}``) ou um campo por variável,
  ``PORTAL_SEGREDO_<CHAVE>__<CAMPO>`` (``PORTAL_SEGREDO_DOMINIO__SENHA``). A chave fica em
  maiúsculas e o que não é letra ou número vira ``_``.
- Modo agente: o Agent ainda não entrega segredos; ``segredo()`` avisa com ``SegredoIndisponivel``.

O valor fica só na memória do processo. O SDK troca os campos **ocultos** por ``***`` em todo
evento antes de gravar na fila local ou enviar, e o Portal faz o mesmo ao receber. Campos
visíveis (usuário, banco) não são mascarados.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator, Mapping
from typing import Any

MASCARA = "***"
MINIMO_PARA_MASCARAR = 4  # valor curto demais apagaria palavras comuns do log
_CHAVE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,159}$")


class SegredoIndisponivel(RuntimeError):
    """O segredo não veio: não liberado para a automação, desativado, vencido, Portal fora do ar
    ou modo sem suporte. A mensagem diz qual chave e por quê, nunca o valor."""


class Segredo(Mapping[str, str]):
    """Os campos de um segredo. ``repr`` e ``str`` nunca mostram valores."""

    def __init__(self, chave: str, campos: dict[str, str], ocultos: list[str]) -> None:
        self.chave = chave
        self._campos = dict(campos)
        self.ocultos = frozenset(ocultos)

    def __getitem__(self, campo: str) -> str:
        try:
            return self._campos[campo]
        except KeyError:
            raise KeyError(f"o segredo {self.chave} não tem o campo {campo!r} (tem: {', '.join(self._campos) or 'nenhum'})") from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._campos)

    def __len__(self) -> int:
        return len(self._campos)

    def __repr__(self) -> str:
        return f"Segredo({self.chave}: {', '.join(self._campos)})"

    __str__ = __repr__

    def para_mascarar(self) -> list[str]:
        return [v for c, v in self._campos.items() if c in self.ocultos and len(v) >= MINIMO_PARA_MASCARAR]


def normalizar(chave: str) -> str:
    texto = str(chave or "").strip().lower().replace(" ", "_")
    if not _CHAVE.match(texto):
        raise ValueError(f"chave de segredo inválida: {chave!r} (letras minúsculas, números, ponto, hífen e sublinhado)")
    return texto


def variavel_local(chave: str) -> str:
    return "PORTAL_SEGREDO_" + re.sub(r"[^A-Z0-9]", "_", normalizar(chave).upper())


def do_ambiente(chaves: list[str], ambiente: Any = None) -> dict[str, Any]:
    """Modo desligado: todos os campos contam como ocultos."""
    env = os.environ if ambiente is None else ambiente
    achados: dict[str, Any] = {}
    negados: dict[str, str] = {}
    for chave in chaves:
        base = variavel_local(chave)
        campos: dict[str, str] = {}
        bruto = env.get(base)
        if bruto:
            try:
                lido = json.loads(bruto)
            except ValueError:
                lido = None
            if isinstance(lido, dict):
                campos = {str(k): str(v) for k, v in lido.items()}
            else:
                campos = {"valor": bruto}
        prefixo = base + "__"
        campos.update({nome[len(prefixo):].lower(): valor for nome, valor in env.items() if nome.startswith(prefixo) and valor})
        if campos:
            achados[chave] = {"campos": campos, "ocultos": list(campos)}
        else:
            negados[chave] = f"modo desligado: defina {base} (JSON) ou {base}__<CAMPO> no ambiente para testar"
    return {"segredos": achados, "negados": negados}


def mascarar(dado: Any, valores: list[str]) -> Any:
    if not valores:
        return dado
    if isinstance(dado, str):
        for valor in valores:
            if valor in dado:
                dado = dado.replace(valor, MASCARA)
        return dado
    if isinstance(dado, dict):
        return {k: mascarar(v, valores) for k, v in dado.items()}
    if isinstance(dado, (list, tuple)):
        return [mascarar(v, valores) for v in dado]
    return dado
