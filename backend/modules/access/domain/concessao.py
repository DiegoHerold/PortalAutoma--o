"""Concessões por automação (decisão 6 da Fase 0).

Cada automação tem quem pode o quê, por usuário ou por time. ``ver_telas_e_logs``,
``editar_itens`` e ``controlar`` só existem por concessão explícita (ou para o
administrador): imagens e logs mostram dados de clientes. ``ver_execucoes`` e
``executar`` continuam valendo também pela permissão antiga da categoria, para não
tirar o acesso de quem já tem.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

VER_EXECUCOES = "ver_execucoes"
VER_TELAS_E_LOGS = "ver_telas_e_logs"
EDITAR_ITENS = "editar_itens"
EXECUTAR = "executar"
CONTROLAR = "controlar"

ACOES = (VER_EXECUCOES, VER_TELAS_E_LOGS, EDITAR_ITENS, EXECUTAR, CONTROLAR)

# Ação nova -> ação antiga da categoria que também dá o direito.
LEGADO = {VER_EXECUCOES: "can_view", EXECUTAR: "can_execute"}

# Quem pode ver telas e logs também pode ver as execuções; quem controla também executa.
IMPLICA = {VER_TELAS_E_LOGS: (VER_EXECUCOES,), CONTROLAR: (EXECUTAR, VER_EXECUCOES), EXECUTAR: (VER_EXECUCOES,),
           EDITAR_ITENS: (VER_EXECUCOES,)}

CENTRAL_DE_TELAS = "central_de_telas"


class AcaoInvalida(ValueError):
    pass


def normalizar_acoes(acoes: Iterable[str]) -> tuple[str, ...]:
    """Ações na ordem oficial, sem repetição. Ação desconhecida é recusada."""
    lista = list(acoes)
    desconhecidas = sorted(set(lista) - set(ACOES))
    if desconhecidas:
        raise AcaoInvalida(f"Ação desconhecida: {', '.join(desconhecidas)}. Use: {', '.join(ACOES)}.")
    return tuple(a for a in ACOES if a in set(lista))


def efetivas(concedidas: Iterable[str]) -> frozenset[str]:
    """Ações concedidas mais as que elas implicam."""
    saida = set(concedidas)
    for acao in list(saida):
        saida.update(IMPLICA.get(acao, ()))
    return frozenset(saida)


def permitido(acao: str, *, admin: bool, concedidas: Iterable[str], legado_permite: Callable[[str], bool]) -> bool:
    if acao not in ACOES:
        raise AcaoInvalida(f"Ação desconhecida: {acao}.")
    if admin:
        return True
    if acao in efetivas(concedidas):
        return True
    antiga = LEGADO.get(acao)
    return antiga is not None and legado_permite(antiga)
