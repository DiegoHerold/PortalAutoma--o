"""Papéis globais (12/11/2026): criar, alterar as abas, renomear e apagar. Só administradores.

- O papel Admin vê tudo: não muda de abas e não é apagado. Papéis do sistema (Manager,
  Operator, Viewer) mudam de abas, mas não são apagados.
- Criar "baseado em" outro papel copia as permissões e as abas dele.
- Ligar uma aba dá ao papel a permissão de leitura dela (ver ``domain.abas``).
- Apagar um papel com pessoas exige o papel para onde elas vão.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from modules.access.domain.abas import (
    ABAS,
    PapelInvalido,
    abas_efetivas,
    permissoes_para_ligar,
    slug_do_nome,
    validar_abas,
)

ADMIN = "admin"
SISTEMA = frozenset({"admin", "manager", "operator", "viewer"})


class PapelNaoEncontrado(LookupError):
    pass


class RepositorioDePapeis(Protocol):
    def listar(self) -> list[dict[str, Any]]: ...
    def obter(self, papel_id: int) -> dict[str, Any] | None: ...
    def slugs(self) -> set[str]: ...
    def nome_em_uso(self, nome: str, exceto: int | None = None) -> bool: ...
    def criar(self, *, nome: str, slug: str, descricao: str | None, abas: list[str]) -> int: ...
    def alterar(self, papel_id: int, campos: dict[str, Any]) -> None: ...
    def permissoes(self, papel_id: int) -> set[str]: ...
    def dar_permissoes(self, papel_id: int, chaves: list[str]) -> None: ...
    def mover_pessoas(self, de: int, para: int) -> int: ...
    def apagar(self, papel_id: int) -> None: ...


def _catalogo() -> list[dict[str, str]]:
    return [{"chave": a.chave, "rotulo": a.rotulo, "grupo": a.grupo} for a in ABAS]


class Papeis:
    def __init__(self, repo: RepositorioDePapeis, audit: Any, transaction: Any) -> None:
        self.repo = repo
        self.audit = audit
        self.transaction = transaction

    # -- leitura ------------------------------------------------------------------
    def abas(self) -> list[dict[str, str]]:
        return _catalogo()

    def listar(self) -> list[dict[str, Any]]:
        return [self._saida(p) for p in self.repo.listar()]

    def _saida(self, p: dict[str, Any]) -> dict[str, Any]:
        admin = p["slug"] == ADMIN
        return {"id": p["id"], "nome": p["nome"], "slug": p["slug"], "descricao": p["descricao"],
                "sistema": p["slug"] in SISTEMA, "pessoas": p["pessoas"],
                "abas": abas_efetivas(None if admin else p["abas"]),
                "pode_mudar_abas": not admin, "pode_apagar": p["slug"] not in SISTEMA}

    def _obter(self, papel_id: int) -> dict[str, Any]:
        papel = self.repo.obter(papel_id)
        if papel is None:
            raise PapelNaoEncontrado("Papel não encontrado.")
        return papel

    # -- escrita ------------------------------------------------------------------
    def criar(self, ator: str | None, *, nome: str, descricao: str | None, abas: list[str] | None,
              baseado_em: int | None) -> dict[str, Any]:
        nome = _nome(nome)
        if self.repo.nome_em_uso(nome):
            raise PapelInvalido("Já existe um papel com esse nome.")
        base = self._obter(baseado_em) if baseado_em else None
        if base is not None and base["slug"] == ADMIN:
            raise PapelInvalido("Para outro administrador, use o próprio papel Admin.")
        escolhidas = validar_abas(abas if abas is not None else (abas_efetivas(base["abas"]) if base else []))
        slug = _slug_livre(slug_do_nome(nome), self.repo.slugs())
        papel_id = self.repo.criar(nome=nome, slug=slug, descricao=_descricao(descricao), abas=escolhidas)
        if base is not None:
            self.repo.dar_permissoes(papel_id, sorted(self.repo.permissoes(base["id"])))
        self.repo.dar_permissoes(papel_id, permissoes_para_ligar(escolhidas))
        self._auditar(ator, "papel.criado", papel_id, None, {"nome": nome, "slug": slug, "abas": escolhidas,
                                                             "baseado_em": base["slug"] if base else None})
        self.transaction.commit()
        return self._saida(self._obter(papel_id))

    def alterar(self, ator: str | None, papel_id: int, *, nome: str | None = None, descricao: str | None = None,
                abas: list[str] | None = None) -> dict[str, Any]:
        papel = self._obter(papel_id)
        campos: dict[str, Any] = {}
        if nome is not None:
            campos["nome"] = _nome(nome)
            if self.repo.nome_em_uso(campos["nome"], exceto=papel_id):
                raise PapelInvalido("Já existe um papel com esse nome.")
        if descricao is not None:
            campos["descricao"] = _descricao(descricao)
        if abas is not None:
            if papel["slug"] == ADMIN:
                raise PapelInvalido("O papel Admin vê todas as abas.")
            campos["abas"] = validar_abas(abas)
        if not campos:
            return self._saida(papel)
        self.repo.alterar(papel_id, campos)
        if "abas" in campos:
            self.repo.dar_permissoes(papel_id, permissoes_para_ligar(campos["abas"]))
        antes = {k: (abas_efetivas(papel["abas"]) if k == "abas" else papel[k]) for k in campos}
        self._auditar(ator, "papel.alterado", papel_id, antes, campos)
        self.transaction.commit()
        return self._saida(self._obter(papel_id))

    def apagar(self, ator: str | None, papel_id: int, *, substituto: int | None) -> dict[str, Any]:
        papel = self._obter(papel_id)
        if papel["slug"] in SISTEMA:
            raise PapelInvalido("Papel do sistema não pode ser apagado.")
        movidas = 0
        if papel["pessoas"]:
            if not substituto or substituto == papel_id:
                raise PapelInvalido(f"{papel['pessoas']} pessoa(s) têm este papel: escolha para qual papel elas vão.")
            destino = self._obter(substituto)
            movidas = self.repo.mover_pessoas(papel_id, destino["id"])
        self.repo.apagar(papel_id)
        self._auditar(ator, "papel.apagado", papel_id, {"nome": papel["nome"], "slug": papel["slug"],
                                                        "abas": abas_efetivas(papel["abas"])},
                      {"pessoas_movidas": movidas, "para": substituto if movidas else None})
        self.transaction.commit()
        return {"id": papel_id, "pessoas_movidas": movidas}

    def _auditar(self, ator: str | None, acao: str, papel_id: int, antes: dict[str, Any] | None,
                 depois: dict[str, Any] | None) -> None:
        from modules.governance.domain.audit import AuditEvent

        self.audit.append(AuditEvent(id=f"aud_{uuid4().hex}", actor_type="user", actor_id=ator, action=acao,
                                     resource_type="role", resource_id=str(papel_id), before=antes, after=depois,
                                     occurred_at=datetime.now(UTC)))


def _nome(nome: str | None) -> str:
    limpo = " ".join(str(nome or "").split())
    if not 2 <= len(limpo) <= 100:
        raise PapelInvalido("O nome do papel vai de 2 a 100 caracteres.")
    return limpo


def _descricao(descricao: str | None) -> str | None:
    limpo = " ".join(str(descricao or "").split())
    return limpo[:500] or None


def _slug_livre(slug: str, usados: set[str]) -> str:
    if slug not in usados:
        return slug
    n = 2
    while f"{slug}-{n}"[:50] in usados:
        n += 1
    return f"{slug}-{n}"[:50]
