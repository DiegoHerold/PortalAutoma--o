"""Funcionalidades do Portal e os papéis (12/11/2026).

A organização do acesso:

- **Papel**: o que a pessoa usa no Portal. Cada funcionalidade (uma por item do menu) fica
  em ``—`` (não entra), ``ver`` ou ``gerenciar`` (vê e altera). Uma pessoa, um papel.
- **Time**: em quais automações ela trabalha (categorias e ações: ver, executar, parar...).
- **Automação, aba Acessos**: as exceções.

Cada nível dá à pessoa a chave própria (``historico.ver``, ``usuarios.gerenciar``...), que é o
que as telas e a API conferem, e as permissões técnicas antigas que aquela área já usava
(``automation.read``...). ``gerenciar`` inclui ``ver``.

**Funcionalidade nova:** acrescente uma ``Funcionalidade`` em ``FUNCIONALIDADES``, confira a chave
dela na API (``<chave>.ver`` / ``<chave>.gerenciar``) e ponha ``funcionalidade`` no item do menu
(``frontend/src/lib/navigation.ts``). Ela aparece na tabela de Papéis com ``—`` em todos os papéis
menos o Admin, até um administrador liberar.

**Papéis de antes** (sem a tabela salva, ``roles.funcionalidades`` nulo): o nível de cada
funcionalidade é deduzido das permissões gravadas e do nome do papel, exatamente como o menu e a
API decidiam antes; as permissões gravadas continuam valendo. Na primeira vez que um
administrador salva a tabela de um papel, ela passa a mandar.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

VER, GERENCIAR = "ver", "gerenciar"
NIVEIS = (VER, GERENCIAR)
ADMIN, GESTOR = "admin", "manager"


@dataclass(frozen=True)
class Funcionalidade:
    chave: str
    nome: str
    grupo: str
    href: str
    # O que "ver" e "gerenciar" dão, além da chave própria (permissões técnicas que a área usa).
    ver_da: tuple[str, ...] = ()
    gerenciar_da: tuple[str, ...] | None = None  # None: a funcionalidade só tem "ver"
    o_que_gerenciar: str = ""
    # Para deduzir o nível dos papéis de antes (como o menu e a API decidiam).
    ver_se: tuple[str, ...] = ()
    gerenciar_se: tuple[str, ...] = ()
    sempre_ver: bool = False  # aparecia para qualquer pessoa logada
    do_gestor: bool = False  # era liberada pelo nome do papel (admin ou manager)

    @property
    def niveis(self) -> tuple[str, ...]:
        return NIVEIS if self.gerenciar_da is not None else (VER,)


_EXEC = ("execution.create", "execution.cancel", "execution.retry")
_FLUXO = ("flow.create", "flow.update", "flow.publish", "flow.execute")

FUNCIONALIDADES: tuple[Funcionalidade, ...] = (
    # Monitorar
    Funcionalidade("painel", "Painel", "Monitorar", "/dashboard", gerenciar_da=("central_de_telas",),
                   o_que_gerenciar="Central de telas: vê as telas de todas as máquinas", sempre_ver=True,
                   gerenciar_se=("central_de_telas",)),
    Funcionalidade("fila", "Fila", "Monitorar", "/fila", gerenciar_da=(),
                   o_que_gerenciar="Reordenar, cancelar na fila e decidir jobs perdidos",
                   ver_se=("execution.read", "automation.read"), gerenciar_se=("execution.cancel",)),
    Funcionalidade("maquinas", "Máquinas", "Monitorar", "/maquinas", gerenciar_da=(),
                   o_que_gerenciar="Cadastrar e apagar máquinas, aprovar automações diretas",
                   ver_se=("execution.read", "agent.read"), do_gestor=True),
    Funcionalidade("historico", "Histórico", "Monitorar", "/historico", ver_se=("execution.read", "flow.read")),
    # Operação
    Funcionalidade("execucoes", "Execuções", "Operação", "/executions", ver_da=("execution.read",), gerenciar_da=_EXEC,
                   o_que_gerenciar="Criar, cancelar e repetir execuções", ver_se=("execution.read", "flow.read"),
                   gerenciar_se=_EXEC),
    Funcionalidade("fluxos", "Fluxos", "Operação", "/flows", ver_da=("flow.read",), gerenciar_da=_FLUXO,
                   o_que_gerenciar="Criar, editar, publicar e executar fluxos", ver_se=("flow.read",), gerenciar_se=_FLUXO),
    Funcionalidade("webhooks", "Webhooks", "Operação", "/webhooks", ver_da=("flow.read",), gerenciar_da=_FLUXO,
                   o_que_gerenciar="Criar e editar webhooks", ver_se=("flow.read",), gerenciar_se=_FLUXO),
    Funcionalidade("agendamentos", "Agendamentos", "Operação", "/schedules", ver_da=("schedule.read",),
                   gerenciar_da=("schedule.create", "schedule.update", "schedule.trigger"),
                   o_que_gerenciar="Criar, mudar e disparar agendamentos", ver_se=("schedule.read",),
                   gerenciar_se=("schedule.create", "schedule.update")),
    # Catálogo
    Funcionalidade("automacoes", "Automações", "Catálogo", "/automations", ver_da=("automation.read",),
                   gerenciar_da=("automation.create", "automation.update", "automation.publish", "automation.block"),
                   o_que_gerenciar="Cadastrar, importar, publicar e dar acessos às automações",
                   ver_se=("automation.read",), gerenciar_se=("automation.create", "automation.update"), do_gestor=True),
    Funcionalidade("categorias", "Categorias", "Catálogo", "/categories", gerenciar_da=(),
                   o_que_gerenciar="Criar, editar e apagar categorias", sempre_ver=True, do_gestor=True),
    Funcionalidade("runtimes", "Runtimes", "Catálogo", "/runtimes", ver_da=("runtime.read",), gerenciar_da=("runtime.manage",),
                   o_que_gerenciar="Cadastrar runtimes", ver_se=("runtime.read",), gerenciar_se=("runtime.manage",)),
    # Infraestrutura
    Funcionalidade("agents", "Agents", "Infraestrutura", "/workers", ver_da=("agent.read",),
                   gerenciar_da=("agent.manage", "agent.update", "agent.disable", "agent.diagnose"),
                   o_que_gerenciar="Ligar, desligar, atualizar e diagnosticar Agents", ver_se=("agent.read",),
                   gerenciar_se=("agent.manage",)),
    Funcionalidade("armazenamento", "Armazenamento", "Infraestrutura", "/storage", ver_da=("artifact.read", "artifact.download"),
                   ver_se=("artifact.read",)),
    # Segurança
    Funcionalidade("auditoria", "Auditoria", "Segurança", "/audit", ver_da=("audit.read",), ver_se=("audit.read",)),
    Funcionalidade("segredos", "Segredos", "Segurança", "/secrets", ver_da=("secret.read_metadata",),
                   gerenciar_da=("secret.manage",), o_que_gerenciar="Criar e trocar segredos",
                   ver_se=("secret.read_metadata",), gerenciar_se=("secret.manage",)),
    Funcionalidade("contas_de_servico", "Contas de serviço", "Segurança", "/service-accounts", gerenciar_da=(),
                   o_que_gerenciar="Criar, revogar e apagar contas de serviço",
                   ver_se=("admin.system",), gerenciar_se=("admin.system",)),
    # Pessoas e acesso
    Funcionalidade("usuarios", "Usuários", "Pessoas e acesso", "/users", gerenciar_da=(),
                   o_que_gerenciar="Criar, editar e desativar pessoas; escolher papel e times",
                   ver_se=("admin.users",), gerenciar_se=("admin.users",), do_gestor=True),
    Funcionalidade("times", "Times", "Pessoas e acesso", "/teams", gerenciar_da=(),
                   o_que_gerenciar="Criar times, pôr pessoas e dar acesso às automações",
                   ver_se=("admin.users",), gerenciar_se=("admin.users",), do_gestor=True),
    # Mudar os papéis é só do Admin (decisão de 12/11/2026): aqui só se libera ver.
    Funcionalidade("papeis", "Papéis", "Pessoas e acesso", "/roles", ver_se=("admin.roles",)),
    Funcionalidade("organizacoes", "Organizações", "Pessoas e acesso", "/organizations", gerenciar_da=(),
                   o_que_gerenciar="Criar e editar organizações", ver_se=("admin.system",),
                   gerenciar_se=("admin.system",), do_gestor=True),
    # Governança
    Funcionalidade("limites", "Limites", "Governança", "/governance/limits", gerenciar_da=(),
                   o_que_gerenciar="Mudar os limites do sistema", ver_se=("admin.system",), gerenciar_se=("admin.system",)),
    Funcionalidade("retencao", "Retenção", "Governança", "/governance/retention", gerenciar_da=(),
                   o_que_gerenciar="Mudar por quanto tempo telas, logs e arquivos ficam guardados",
                   ver_se=("admin.system",), gerenciar_se=("admin.system",)),
)
POR_CHAVE = {f.chave: f for f in FUNCIONALIDADES}

# Abas da etapa anterior (lista de hrefs em ``roles.abas``), para deduzir os papéis já ajustados.
_POR_HREF = {f.href: f for f in FUNCIONALIDADES}
_ABAS_DE_ANTES = frozenset({"/fila", "/maquinas", "/historico", "/executions", "/flows", "/webhooks", "/schedules",
                            "/automations", "/categories", "/runtimes", "/workers", "/storage", "/audit", "/secrets",
                            "/users", "/roles"})


# O que cada aba desligada tirava na etapa anterior (só as permissões que eram só dela).
_EXCLUSIVAS_DE_ANTES = {
    "/schedules": ("schedule.read", "schedule.create", "schedule.update", "schedule.trigger"),
    "/runtimes": ("runtime.read", "runtime.manage"), "/audit": ("audit.read",),
    "/secrets": ("secret.read_metadata", "secret.manage"), "/users": ("admin.users",), "/roles": ("admin.roles",),
}


class FuncionalidadeInvalida(ValueError):
    pass


def chave(funcionalidade: str, nivel: str) -> str:
    return f"{funcionalidade}.{nivel}"


def validar(tabela: Mapping[str, str | None]) -> dict[str, str]:
    """``{funcionalidade: "ver"|"gerenciar"}``, só as ligadas, na ordem do menu."""
    saida: dict[str, str] = {}
    for chave_f, nivel in tabela.items():
        f = POR_CHAVE.get(chave_f)
        if f is None:
            raise FuncionalidadeInvalida(f"funcionalidade desconhecida: {chave_f}")
        if nivel in (None, "", "nenhum"):
            continue
        if nivel not in f.niveis:
            raise FuncionalidadeInvalida(f"{f.nome}: nível {nivel!r} não existe (use {' ou '.join(f.niveis)})")
        saida[chave_f] = nivel
    return {f.chave: saida[f.chave] for f in FUNCIONALIDADES if f.chave in saida}


def deduzir(slug: str | None, gravadas: Iterable[str], abas: list[str] | None = None) -> dict[str, str]:
    """O nível de cada funcionalidade num papel de antes, igual ao que o menu e a API faziam."""
    if slug == ADMIN:
        return {f.chave: f.niveis[-1] for f in FUNCIONALIDADES}
    tem = set(gravadas)
    gestor = slug == GESTOR
    saida: dict[str, str] = {}
    for f in FUNCIONALIDADES:
        if abas is not None and f.href in _ABAS_DE_ANTES and f.href not in abas:
            continue
        ve = f.sempre_ver or bool(tem & set(f.ver_se)) or (f.do_gestor and gestor)
        if not ve:
            continue
        gerencia = f.gerenciar_da is not None and (bool(tem & set(f.gerenciar_se)) or (f.do_gestor and gestor))
        saida[f.chave] = GERENCIAR if gerencia else VER
    return saida


def permissoes_da_tabela(tabela: Mapping[str, str]) -> set[str]:
    """As chaves que a tabela dá: a própria de cada nível e as técnicas da área."""
    saida: set[str] = set()
    for chave_f, nivel in tabela.items():
        f = POR_CHAVE.get(chave_f)
        if f is None or nivel not in f.niveis:
            continue
        saida.add(chave(f.chave, VER))
        saida.update(f.ver_da)
        if nivel == GERENCIAR:
            saida.add(chave(f.chave, GERENCIAR))
            saida.update(f.gerenciar_da or ())
    return saida


def permissoes_efetivas(slug: str | None, gravadas: Iterable[str], abas: list[str] | None,
                        tabela: Mapping[str, str] | None) -> list[str]:
    """O que o papel pode, para a API e para a tela.

    - Tabela salva: só o que ela dá.
    - Papel de antes: as permissões gravadas (como antes, menos as das abas desligadas) mais as
      chaves das funcionalidades deduzidas.
    """
    if tabela is not None:
        return sorted(permissoes_da_tabela(tabela))
    lista = list(gravadas)
    if abas is not None:
        fora = {p for href, chaves in _EXCLUSIVAS_DE_ANTES.items() if href not in abas for p in chaves}
        lista = [p for p in lista if p not in fora]
    deduzidas = deduzir(slug, lista, abas)
    return sorted(set(lista) | {k for k in permissoes_da_tabela(deduzidas) if "." in k and k.split(".")[0] in POR_CHAVE})


def catalogo() -> list[dict[str, object]]:
    return [{"chave": f.chave, "nome": f.nome, "grupo": f.grupo, "href": f.href, "niveis": list(f.niveis),
             "o_que_gerenciar": f.o_que_gerenciar or None} for f in FUNCIONALIDADES]
