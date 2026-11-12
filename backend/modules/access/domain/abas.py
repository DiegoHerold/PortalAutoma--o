"""Abas do menu que cada papel vê (12/11/2026).

Só administradores mudam. Para cada aba:

- ``permissao``: a permissão de leitura que o papel ganha quando a aba é ligada (para a aba
  aparecer e os dados abrirem);
- ``exclusivas``: permissões que só aquela aba usa. Com a aba desligada, o papel perde essas
  permissões também no backend (a API recusa), mesmo que estejam gravadas: ligar de novo devolve.

As abas que dividem permissão com outras (Fila, Máquinas, Histórico e Execuções usam
``execution.read``) são bloqueadas na tela. Painel e Configurações aparecem sempre; as áreas
só de administradores e gestores (Times, Organizações, Contas de serviço, Limites, Retenção)
seguem essa regra e não entram aqui. O papel Admin vê tudo e não é editável.

A lista espelha ``frontend/src/lib/navigation.ts``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Aba:
    chave: str
    rotulo: str
    grupo: str
    permissao: str | None = None
    exclusivas: tuple[str, ...] = ()


ABAS: tuple[Aba, ...] = (
    Aba("/fila", "Fila", "Monitorar", "execution.read"),
    Aba("/maquinas", "Máquinas", "Monitorar", "execution.read"),
    Aba("/historico", "Histórico", "Monitorar", "execution.read"),
    Aba("/executions", "Execuções", "Operação", "execution.read"),
    Aba("/flows", "Fluxos", "Operação", "flow.read"),
    Aba("/webhooks", "Webhooks", "Operação", "flow.read"),
    Aba("/schedules", "Agendamentos", "Operação", "schedule.read",
        ("schedule.read", "schedule.create", "schedule.update", "schedule.trigger")),
    Aba("/automations", "Automações", "Catálogo", "automation.read"),
    Aba("/categories", "Categorias", "Catálogo"),
    Aba("/runtimes", "Runtimes", "Catálogo", "runtime.read", ("runtime.read", "runtime.manage")),
    Aba("/workers", "Agents", "Infraestrutura", "agent.read"),
    Aba("/storage", "Armazenamento", "Infraestrutura", "artifact.read"),
    Aba("/audit", "Auditoria", "Segurança", "audit.read", ("audit.read",)),
    Aba("/secrets", "Segredos", "Segurança", "secret.read_metadata", ("secret.read_metadata", "secret.manage")),
    Aba("/users", "Usuários", "Pessoas e acesso", "admin.users", ("admin.users",)),
    Aba("/roles", "Papéis", "Pessoas e acesso", "admin.roles", ("admin.roles",)),
)
CHAVES = tuple(a.chave for a in ABAS)
POR_CHAVE = {a.chave: a for a in ABAS}


class PapelInvalido(ValueError):
    pass


def validar_abas(abas: Iterable[str]) -> list[str]:
    """Na ordem do menu, sem repetir. Aba desconhecida é erro (não se grava lixo)."""
    escolhidas = set(abas)
    desconhecidas = escolhidas - set(CHAVES)
    if desconhecidas:
        raise PapelInvalido(f"aba desconhecida: {', '.join(sorted(desconhecidas))}")
    return [c for c in CHAVES if c in escolhidas]


def abas_efetivas(abas: list[str] | None) -> list[str]:
    """Nulo (papel de antes) = todas."""
    return list(CHAVES) if abas is None else [c for c in CHAVES if c in set(abas)]


def permissoes_com_abas(permissoes: Iterable[str], abas: list[str] | None) -> list[str]:
    """Tira as permissões exclusivas das abas desligadas."""
    lista = list(permissoes)
    if abas is None:
        return lista
    ligadas = set(abas)
    fora = {p for a in ABAS if a.chave not in ligadas for p in a.exclusivas}
    return [p for p in lista if p not in fora]


def permissoes_para_ligar(abas: Iterable[str]) -> list[str]:
    """As permissões de leitura que as abas ligadas precisam."""
    return sorted({POR_CHAVE[c].permissao for c in abas if POR_CHAVE[c].permissao})


def slug_do_nome(nome: str) -> str:
    """"Analista Fiscal" -> "analista-fiscal"."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    if not slug:
        raise PapelInvalido("o nome precisa de letras ou números")
    return slug[:50]
