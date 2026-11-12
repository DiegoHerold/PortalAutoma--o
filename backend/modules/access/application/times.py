"""Casos de uso dos times: membros, times de uma pessoa e permissões por categoria.

Quem cuida dos times é quem cuida dos usuários (``admin.users``), como no cadastro do time.
Toda mudança vai para a auditoria com o antes e o depois.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AccessResourceNotFound
from modules.access.domain.times import TimeInvalido, validar_categorias, validar_membros
from modules.governance.domain.audit import AuditEvent


class GerenciarTimes:
    def __init__(self, access: Any, times: Any, audit: Any, transaction: Any) -> None:
        self.access = access
        self.times = times
        self.audit = audit
        self.transaction = transaction

    def _garantir(self, ator: Any, team_id: int | None = None, nivel: str = "gerenciar") -> None:
        PermissionChecker(self.access).ensure_permission(ator, f"times.{nivel}")
        if team_id is not None and self.times.time(team_id) is None:
            raise AccessResourceNotFound("Time não encontrado.")

    def _auditar(self, ator: Any, acao: str, tipo: str, recurso: str, antes: Any, depois: Any) -> None:
        self.audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(ator, "id", "")) or None, action=acao,
            resource_type=tipo, resource_id=recurso, before=antes, after=depois, occurred_at=datetime.now(UTC)))

    # -- leitura -------------------------------------------------------------------------------
    def ver(self, ator: Any, team_id: int) -> dict[str, Any]:
        self._garantir(ator, team_id, "ver")
        return {"membros": self.times.membros(team_id), "categorias": self.times.categorias(team_id),
                "automacoes": self.times.automacoes(team_id)}

    # -- membros ---------------------------------------------------------------------------------
    def adicionar_membros(self, ator: Any, team_id: int, brutos: Any) -> list[dict[str, Any]]:
        self._garantir(ator, team_id)
        pedidos = set(validar_membros(brutos))
        faltam = pedidos - self.times.usuarios_existentes(sorted(pedidos))
        if faltam:
            raise AccessResourceNotFound(f"Usuário não encontrado: {', '.join(map(str, sorted(faltam)))}.")
        novos = pedidos - self.times.ids_dos_membros(team_id)
        if novos:
            self.times.adicionar_membros(team_id, novos)
            self._auditar(ator, "time.membros.adicionados", "team", str(team_id), None, {"usuarios": sorted(novos)})
        self.transaction.commit()
        return self.times.membros(team_id)

    def remover_membro(self, ator: Any, team_id: int, user_id: int) -> list[dict[str, Any]]:
        self._garantir(ator, team_id)
        if user_id not in self.times.ids_dos_membros(team_id):
            raise AccessResourceNotFound("Essa pessoa não é membro do time.")
        self.times.remover_membros(team_id, {user_id})
        self._auditar(ator, "time.membro.removido", "team", str(team_id), {"usuario": user_id}, None)
        self.transaction.commit()
        return self.times.membros(team_id)

    def times_do_usuario(self, ator: Any, user_id: int) -> list[dict[str, Any]]:
        self._garantir(ator, nivel="ver")
        return self.times.times_do_usuario(user_id)

    def definir_times_do_usuario(self, ator: Any, user_id: int, brutos: Any) -> list[dict[str, Any]]:
        """Os times de uma pessoa (no cadastro do usuário): a lista enviada passa a ser a dela."""
        self._garantir(ator)
        if not self.times.usuarios_existentes([user_id]):
            raise AccessResourceNotFound("Usuário não encontrado.")
        pedidos = set(validar_membros(brutos, "times")) if brutos != [] else set()
        faltam = pedidos - self.times.times_existentes(sorted(pedidos))
        if faltam:
            raise AccessResourceNotFound(f"Time não encontrado: {', '.join(map(str, sorted(faltam)))}.")
        entram, saem = self.times.definir_times_do_usuario(user_id, pedidos)
        if entram or saem:
            self._auditar(ator, "usuario.times.definidos", "user", str(user_id), {"saiu_de": sorted(saem)},
                          {"entrou_em": sorted(entram)})
        self.transaction.commit()
        return self.times.times_do_usuario(user_id)

    # -- permissões por categoria ---------------------------------------------------------------
    def definir_categorias(self, ator: Any, team_id: int, brutas: Any) -> list[dict[str, Any]]:
        self._garantir(ator, team_id)
        permissoes = validar_categorias(brutas)
        faltam = {p.category_id for p in permissoes} - self.times.categorias_existentes([p.category_id for p in permissoes])
        if faltam:
            raise AccessResourceNotFound(f"Categoria não encontrada: {', '.join(map(str, sorted(faltam)))}.")
        antes = self.times.categorias(team_id)
        self.times.definir_categorias(team_id, permissoes)
        depois = self.times.categorias(team_id)
        if antes != depois:
            self._auditar(ator, "time.categorias.definidas", "team", str(team_id),
                          {"categorias": _resumo(antes)}, {"categorias": _resumo(depois)})
        self.transaction.commit()
        return depois


def _resumo(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in linha.items() if k != "categoria"} for linha in linhas]


__all__ = ["GerenciarTimes", "TimeInvalido"]
