"""Segredos (0.5.0): senhas e chaves que a automação recebe do Portal durante a execução.

- Modo direto: o SDK pede ao Portal com o token do job (``POST .../segredos``). Só sai o que
  está ligado à automação no Portal (aba Técnico), ativo e dentro da validade.
- Modo desligado (desenvolvimento): lê ``PORTAL_SEGREDO_<CHAVE>`` do ambiente, com a chave em
  maiúsculas e o que não é letra ou número trocado por ``_`` (``dominio.senha_banco`` →
  ``PORTAL_SEGREDO_DOMINIO_SENHA_BANCO``).
- Modo agente: o Agent ainda não entrega segredos; ``segredo()`` avisa com ``SegredoIndisponivel``.

O valor fica só na memória do processo. O SDK troca o valor por ``***`` em todo evento antes
de gravar na fila local ou enviar, e o Portal faz o mesmo ao receber.
"""

from __future__ import annotations

import os
import re
from typing import Any

MASCARA = "***"
MINIMO_PARA_MASCARAR = 4  # valor curto demais apagaria palavras comuns do log
_CHAVE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,159}$")


class SegredoIndisponivel(RuntimeError):
    """O segredo não veio: não liberado para a automação, desativado, vencido, Portal fora do ar
    ou modo sem suporte. A mensagem diz qual chave e por quê, nunca o valor."""


def normalizar(chave: str) -> str:
    texto = str(chave or "").strip().lower().replace(" ", "_")
    if not _CHAVE.match(texto):
        raise ValueError(f"chave de segredo inválida: {chave!r} (letras minúsculas, números, ponto, hífen e sublinhado)")
    return texto


def variavel_local(chave: str) -> str:
    return "PORTAL_SEGREDO_" + re.sub(r"[^A-Z0-9]", "_", normalizar(chave).upper())


def do_ambiente(chaves: list[str], ambiente: Any = None) -> dict[str, Any]:
    env = os.environ if ambiente is None else ambiente
    achados: dict[str, str] = {}
    negados: dict[str, str] = {}
    for chave in chaves:
        valor = env.get(variavel_local(chave))
        if valor:
            achados[chave] = valor
        else:
            negados[chave] = f"modo desligado: defina {variavel_local(chave)} no ambiente para testar"
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
