"""Contas de serviço (13/11/2026): um sistema que chama a API do Portal sem ser uma pessoa.

Modelo de acesso igual ao de uma pessoa: cada conta tem um usuário técnico com **um papel**
(quais áreas da API) e **times** (em quais automações), e pode receber exceções na aba Acessos
da automação. O usuário técnico não entra pela tela de login e não aparece em Usuários.

Credencial: ``psa_`` + 43 caracteres aleatórios, mostrada uma única vez. O Portal guarda só o
SHA-256 e os 4 últimos caracteres (para reconhecer qual está em uso). Uso:
``Authorization: Bearer psa_...``, nunca na URL. Gerar uma nova invalida a anterior na hora.

Recusas: conta desativada, vencida, credencial trocada ou usuário técnico inativo. Cada recusa
de uma credencial ``psa_`` vai para a auditoria (sem a credencial).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AccessResourceNotFound, AuthenticationFailed
from modules.governance.domain.audit import AuditEvent

PREFIXO = "psa_"
SITUACOES = ("active", "disabled")
PAPEL_PROIBIDO = "admin"  # conta de serviço nunca é administradora
INTERVALO_MARCAR_USO = timedelta(seconds=60)


class ContaInvalida(ValueError):
    pass


def hash_da_credencial(credencial: str) -> str:
    return "sha256:" + hashlib.sha256(credencial.encode("utf-8")).hexdigest()


def nova_credencial() -> tuple[str, str, str]:
    credencial = PREFIXO + secrets.token_urlsafe(32)
    return credencial, hash_da_credencial(credencial), credencial[-4:]


def e_credencial_de_conta(token: str | None) -> bool:
    return bool(token) and str(token).startswith(PREFIXO)


class ContasDeServico:
    def __init__(self, access: Any, contas: Any, times: Any, auditoria: Any, agora: Any = None) -> None:
        self.access = access
        self.contas = contas
        self.times = times
        self.auditoria = auditoria
        self._agora = agora or (lambda: datetime.now(UTC))

    # -- autenticação ------------------------------------------------------------------------
    def autenticar(self, credencial: str, *, ip: str | None = None, user_agent: str | None = None) -> Any:
        agora = self._agora()
        conta = self.contas.pelo_hash(hash_da_credencial(credencial))
        motivo = None
        usuario = None
        if conta is None:
            motivo = "credencial_desconhecida"
        elif conta.status != "active":
            motivo = "conta_desativada"
        elif conta.expires_at is not None and conta.expires_at <= agora:
            motivo = "conta_vencida"
        else:
            usuario = self.access.get_user_record(conta.user_id) if conta.user_id is not None else None
            if usuario is None or not usuario.is_active or usuario.status != "active":
                motivo = "usuario_tecnico_inativo"
        if motivo:
            self._auditar(None, "conta_de_servico.recusada", conta.id if conta else "desconhecida",
                          metadados={"motivo": motivo, "ip": ip, "user_agent": (user_agent or "")[:200]}, agora=agora,
                          tipo_ator="service_account", id_ator=conta.id if conta else None)
            raise AuthenticationFailed("Could not validate credentials.")
        if conta.last_used_at is None or agora - conta.last_used_at >= INTERVALO_MARCAR_USO:
            self.contas.marcar_uso(conta, agora)
        usuario.team_category_permissions = self.access.categorias_pelos_times(usuario.id)
        usuario.conta_de_servico_id = conta.id
        return usuario

    # -- leitura -----------------------------------------------------------------------------
    def listar(self, ator: Any) -> list[dict[str, Any]]:
        PermissionChecker(self.access).ensure_permission(ator, "contas_de_servico.ver")
        return [self._dados(c) for c in self.contas.todas()]

    def _dados(self, conta: Any) -> dict[str, Any]:
        agora = self._agora()
        usuario = self.contas.usuario(conta.user_id)
        papel = self.contas.papel(usuario.role_id) if usuario else None
        vencida = conta.expires_at is not None and conta.expires_at <= agora
        return {
            "id": conta.id, "nome": conta.name, "descricao": conta.description,
            "situacao": "active" if conta.status == "active" else "disabled", "vencida": vencida,
            "papel": {"id": papel.id, "nome": papel.name, "slug": papel.slug} if papel else None,
            "times": [{"id": t["id"], "nome": t["nome"]} for t in self.times.times_do_usuario(usuario.id)] if usuario else [],
            "expira_em": conta.expires_at, "ultimo_uso": conta.last_used_at, "criada_em": conta.created_at,
            "credencial_final": conta.credential_hint, "credencial_criada_em": conta.credential_created_at,
            "tem_credencial": bool(conta.credential_hint) and conta.credential_hash.startswith("sha256:"),
            "usuario_id": conta.user_id,
        }

    # -- gestão ----------------------------------------------------------------------------------
    def criar(self, ator: Any, dados: dict[str, Any]) -> dict[str, Any]:
        PermissionChecker(self.access).ensure_permission(ator, "contas_de_servico.gerenciar")
        nome = self._nome(dados.get("nome"))
        papel = self._papel(dados.get("papel_id"))
        times = self._times(dados.get("times", []))
        expira = self._validade(dados.get("expira_em"))
        conta_id = f"sa_{uuid4().hex[:20]}"
        credencial, hash_, final = nova_credencial()
        agora = self._agora()
        conta = self.contas.criar(conta_id=conta_id, nome=nome, descricao=self._descricao(dados.get("descricao")),
                                  role_id=papel.id, organization_id=getattr(ator, "organization_id", None),
                                  credential_hash=hash_, hint=final, expira_em=expira, criado_por=_quem(ator),
                                  senha_inutilizavel=f"!conta-de-servico!{secrets.token_hex(16)}", agora=agora)
        if times:
            self.times.definir_times_do_usuario(conta.user_id, times)
        self._auditar(ator, "conta_de_servico.criada", conta.id,
                      depois={"nome": nome, "papel": papel.slug, "times": sorted(times), "expira_em": _iso(expira)})
        return {"conta": self._dados(conta), "credencial": credencial}

    def mudar(self, ator: Any, conta_id: str, dados: dict[str, Any]) -> dict[str, Any]:
        PermissionChecker(self.access).ensure_permission(ator, "contas_de_servico.gerenciar")
        conta = self._conta(conta_id)
        antes = self._resumo(conta)
        agora = self._agora()
        mudanca: dict[str, Any] = {}
        if "nome" in dados:
            mudanca["name"] = self._nome(dados["nome"], exceto=conta.id)
        if "descricao" in dados:
            mudanca["description"] = self._descricao(dados["descricao"])
        if "expira_em" in dados:
            mudanca["expires_at"] = self._validade(dados["expira_em"])
        if "situacao" in dados:
            if dados["situacao"] not in SITUACOES:
                raise ContaInvalida("Situação: active ou disabled.")
            if dados["situacao"] == "active" and not conta.credential_hash.startswith("sha256:"):
                raise ContaInvalida("Gere uma credencial antes de ativar a conta.")
            mudanca["status"] = dados["situacao"]
        if mudanca:
            self.contas.mudar(conta, mudanca, agora)
        if "papel_id" in dados:
            self.contas.mudar_papel(conta, self._papel(dados["papel_id"]).id, agora)
        if "times" in dados:
            self.times.definir_times_do_usuario(conta.user_id, self._times(dados["times"]))
        depois = self._resumo(conta)
        if antes != depois:
            self._auditar(ator, "conta_de_servico.alterada", conta.id, antes=antes, depois=depois)
        return self._dados(conta)

    def gerar_credencial(self, ator: Any, conta_id: str) -> dict[str, Any]:
        PermissionChecker(self.access).ensure_permission(ator, "contas_de_servico.gerenciar")
        conta = self._conta(conta_id)
        credencial, hash_, final = nova_credencial()
        self.contas.trocar_credencial(conta, hash_, final, self._agora())
        self._auditar(ator, "conta_de_servico.credencial_gerada", conta.id, depois={"credencial_final": final})
        return {"conta": self._dados(conta), "credencial": credencial}

    def apagar(self, ator: Any, conta_id: str) -> None:
        PermissionChecker(self.access).ensure_permission(ator, "contas_de_servico.gerenciar")
        conta = self._conta(conta_id)
        resumo = self._resumo(conta)
        self.contas.apagar(conta)
        self._auditar(ator, "conta_de_servico.apagada", conta_id, antes=resumo)

    # -- validação ----------------------------------------------------------------------------------
    def _conta(self, conta_id: str) -> Any:
        conta = self.contas.conta(conta_id)
        if conta is None:
            raise AccessResourceNotFound("Conta de serviço não encontrada.")
        return conta

    def _nome(self, valor: Any, exceto: str | None = None) -> str:
        nome = str(valor or "").strip()
        if not nome:
            raise ContaInvalida("Dê um nome à conta (o sistema que vai usá-la).")
        if len(nome) > 180:
            raise ContaInvalida("Nome com até 180 caracteres.")
        if self.contas.nome_existe(nome, exceto):
            raise ContaInvalida("Já existe uma conta de serviço com este nome.")
        return nome

    @staticmethod
    def _descricao(valor: Any) -> str | None:
        texto = str(valor or "").strip()
        return texto[:2000] or None

    def _papel(self, valor: Any) -> Any:
        if not isinstance(valor, int) or isinstance(valor, bool):
            raise ContaInvalida("Escolha o papel da conta.")
        papel = self.contas.papel(valor)
        if papel is None:
            raise AccessResourceNotFound("Papel não encontrado.")
        if papel.slug == PAPEL_PROIBIDO:
            raise ContaInvalida("Conta de serviço não pode ter o papel Administrador. Crie um papel só com o que o sistema precisa.")
        return papel

    def _times(self, valor: Any) -> set[int]:
        if valor is None:
            return set()
        if not isinstance(valor, list) or not all(isinstance(t, int) and not isinstance(t, bool) for t in valor):
            raise ContaInvalida("Envie 'times' como uma lista de ids.")
        pedidos = set(valor)
        faltam = pedidos - self.times.times_existentes(sorted(pedidos))
        if faltam:
            raise AccessResourceNotFound(f"Time não encontrado: {', '.join(map(str, sorted(faltam)))}.")
        return pedidos

    def _validade(self, valor: Any) -> datetime | None:
        if valor in (None, ""):
            return None
        try:
            quando = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContaInvalida("Validade em formato de data e hora (ISO 8601).") from exc
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=UTC)
        if quando <= self._agora():
            raise ContaInvalida("A validade precisa ser no futuro.")
        return quando

    def _resumo(self, conta: Any) -> dict[str, Any]:
        usuario = self.contas.usuario(conta.user_id)
        papel = self.contas.papel(usuario.role_id) if usuario else None
        return {"nome": conta.name, "situacao": conta.status, "papel": papel.slug if papel else None,
                "times": sorted(t["id"] for t in self.times.times_do_usuario(conta.user_id)) if conta.user_id else [],
                "expira_em": _iso(conta.expires_at)}

    def _auditar(self, ator: Any, acao: str, recurso: str, *, antes: dict | None = None, depois: dict | None = None,
                 metadados: dict | None = None, agora: datetime | None = None, tipo_ator: str = "user",
                 id_ator: str | None = None) -> None:
        self.auditoria.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type=tipo_ator, actor_id=id_ator if id_ator is not None else _quem(ator),
            action=acao, resource_type="service_account", resource_id=recurso, before=antes, after=depois,
            metadata=metadados or {}, organization_id=getattr(ator, "organization_id", None),
            occurred_at=agora or self._agora()))


def _quem(ator: Any) -> str | None:
    valor = getattr(ator, "id", None)
    return str(valor) if valor is not None else None


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None
