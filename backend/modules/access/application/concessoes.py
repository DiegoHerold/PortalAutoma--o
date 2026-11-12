"""Quem pode o quê em cada automação: consulta e gestão das concessões (com auditoria)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from modules.access.application.use_cases import PermissionChecker, _role_slug
from modules.access.domain import AccessResourceNotFound, AuthorizationDenied, RoleSlug
from modules.access.domain.concessao import AcaoInvalida, normalizar_acoes, permitido
from modules.governance.domain.audit import AuditEvent


class AcessoPorAutomacao:
    def __init__(self, access: Any, grants: Any) -> None:
        self.access = access
        self.grants = grants

    def pode(self, user: Any, automation_id: int, acao: str) -> bool:
        admin = _role_slug(user) == RoleSlug.ADMIN.value
        user_id = getattr(user, "id", None)
        concedidas = self.grants.acoes_do_usuario(int(user_id), automation_id) if user_id is not None and not admin else set()

        def legado_permite(acao_antiga: str) -> bool:
            try:
                PermissionChecker(self.access).ensure_automation_action(user, automation_id, acao_antiga)
                return True
            except (AuthorizationDenied, AccessResourceNotFound):
                return False

        return permitido(acao, admin=admin, concedidas=concedidas, legado_permite=legado_permite)

    def garantir(self, user: Any, automation_id: int | None, acao: str) -> None:
        if automation_id is None or self.access.get_automation_category_id(automation_id) is None:
            raise AccessResourceNotFound("Automação não encontrada.")
        if not self.pode(user, automation_id, acao):
            raise AuthorizationDenied(f"Sem a permissão '{acao}' nesta automação.")


class GerenciarConcessoes:
    """Administrador e gestor concedem e retiram. Toda mudança vai para a auditoria."""

    def __init__(self, access: Any, grants: Any, audit: Any, transaction: Any) -> None:
        self.access = access
        self.grants = grants
        self.audit = audit
        self.transaction = transaction

    def _garantir_gestor(self, ator: Any, automation_id: int) -> None:
        PermissionChecker(self.access).ensure_permission(ator, "automacoes.gerenciar")
        if self.access.get_automation_category_id(automation_id) is None:
            raise AccessResourceNotFound("Automação não encontrada.")

    def listar(self, ator: Any, automation_id: int) -> list[dict[str, Any]]:
        self._garantir_gestor(ator, automation_id)
        return self.grants.listar(automation_id)

    def definir(self, ator: Any, automation_id: int, *, user_id: int | None, team_id: int | None,
                acoes: list[str], agora: datetime) -> dict[str, Any] | None:
        """Grava as ações de um usuário ou de um time. Lista vazia retira a concessão."""
        self._garantir_gestor(ator, automation_id)
        if (user_id is None) == (team_id is None):
            raise AcaoInvalida("Informe um usuário ou um time, não os dois.")
        if user_id is not None and not self.grants.existe_usuario(user_id):
            raise AccessResourceNotFound("Usuário não encontrado.")
        if team_id is not None and not self.grants.existe_time(team_id):
            raise AccessResourceNotFound("Time não encontrado.")
        novas = list(normalizar_acoes(acoes))
        atual = self.grants.buscar(automation_id, user_id=user_id, team_id=team_id)
        antes = {"acoes": list(atual.acoes)} if atual is not None else None
        destino = {"automation_id": automation_id, "user_id": user_id, "team_id": team_id}
        if not novas:
            if atual is None:
                return None
            self.grants.remover(atual)
            self._auditar(ator, "automacao.concessao.retirada", atual.id, antes, {**destino, "acoes": []}, agora)
            self.transaction.commit()
            return None
        registro = self.grants.salvar(grant_id=atual.id if atual else f"agr_{uuid4().hex}", automation_id=automation_id,
                                      user_id=user_id, team_id=team_id, acoes=novas,
                                      por=getattr(ator, "id", None), agora=agora)
        self._auditar(ator, "automacao.concessao.definida", registro.id, antes, {**destino, "acoes": novas}, agora)
        self.transaction.commit()
        return next(g for g in self.grants.listar(automation_id) if g["id"] == registro.id)

    def _auditar(self, ator: Any, acao: str, recurso: str, antes: dict | None, depois: dict, agora: datetime) -> None:
        self.audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(ator, "id", "")) or None, action=acao,
            resource_type="automation_grant", resource_id=recurso, before=antes, after=depois, occurred_at=agora))
