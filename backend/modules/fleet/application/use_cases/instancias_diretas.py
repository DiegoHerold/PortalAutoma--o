"""Inscrição, aprovação e sessão das instâncias diretas (ADR-018, seção 7 da Fase 0).

Fluxo: o administrador gera um código de uso único -> a automação se inscreve com a chave
pública -> fica pendente -> o administrador aprova escolhendo a máquina -> a cada 10
minutos a instância troca um desafio assinado por uma sessão. Tudo auditado.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from modules.fleet.domain.instancia_direta import (
    APROVADA,
    DURACAO_SESSAO,
    PENDENTE,
    QUARENTENA,
    REVOGADA,
    VALIDADE_CODIGO,
    VALIDADE_DESAFIO,
    TransicaoInvalida,
    hash_de,
    mensagem_assinada,
    normalizar_codigo,
    pode_abrir_sessao,
    transicao,
)
from modules.governance.domain.audit import AuditEvent

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I: o código é digitado


class Recusado(Exception):
    """Recusa de credencial. ``motivo`` vai para a auditoria; quem pediu recebe só 401."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class SessaoAberta:
    token: str
    expira_em: datetime
    instancia_id: str
    status: str


@dataclass(frozen=True)
class InstanciaAutenticada:
    id: str
    automation_id: int
    machine_id: str | None
    status: str


def _auditar(audit: Any, *, ator_tipo: str, ator: str | None, acao: str, recurso: str, agora: datetime,
             metadados: dict[str, Any] | None = None, antes: dict | None = None, depois: dict | None = None) -> None:
    audit.append(AuditEvent(id=f"aud_{uuid4().hex}", actor_type=ator_tipo, actor_id=ator, action=acao,
                            resource_type="direct_instance", resource_id=recurso, metadata=metadados or {},
                            before=antes, after=depois, occurred_at=agora))


class GerarCodigoDeInscricao:
    def __init__(self, store: Any, audit: Any, transaction: Any) -> None:
        self.store, self.audit, self.transaction = store, audit, transaction

    def execute(self, *, automation_id: int, por: str, agora: datetime) -> tuple[str, datetime]:
        bruto = "".join(secrets.choice(ALFABETO) for _ in range(16))
        codigo = "-".join(bruto[i:i + 4] for i in range(0, 16, 4))
        expira = agora + VALIDADE_CODIGO
        codigo_id = f"dec_{uuid4().hex}"
        self.store.adicionar_codigo(id=codigo_id, automation_id=automation_id, code_hash=hash_de(codigo),
                                    created_by=por, created_at=agora, expires_at=expira)
        _auditar(self.audit, ator_tipo="user", ator=por, acao="direto.codigo.gerado", recurso=codigo_id, agora=agora,
                 metadados={"automation_id": automation_id, "expira_em": expira.isoformat()})
        self.transaction.commit()
        return codigo, expira


class Inscrever:
    def __init__(self, store: Any, audit: Any, transaction: Any, validar_chave: Callable[[str], str]) -> None:
        self.store, self.audit, self.transaction, self.validar_chave = store, audit, transaction, validar_chave

    def execute(self, *, codigo: str, chave_publica: str, nome: str | None, versao: str | None,
                agora: datetime, ip: str | None = None) -> str:
        normalizado = normalizar_codigo(codigo)
        if normalizado is None:
            raise Recusado("codigo_mal_formado")
        chave = self.validar_chave(chave_publica)  # ChaveInvalida -> 422 (não é credencial errada)
        reservado = self.store.reservar_codigo(hash_de(normalizado), agora)
        if reservado is None:
            raise Recusado("codigo_invalido_vencido_ou_usado")
        codigo_id, automation_id = reservado
        instancia_id = f"dri_{uuid4().hex[:16]}"
        self.store.adicionar_instancia(id=instancia_id, automation_id=automation_id, status=PENDENTE, public_key=chave,
                                       reported_name=(nome or "")[:255] or None, reported_version=(versao or "")[:80] or None,
                                       created_at=agora)
        self.store.marcar_codigo_usado(codigo_id, instancia_id, agora)
        _auditar(self.audit, ator_tipo="direct_instance", ator=instancia_id, acao="direto.inscricao", recurso=instancia_id,
                 agora=agora, metadados={"automation_id": automation_id, "nome_informado": nome, "versao": versao, "ip": ip})
        self.transaction.commit()
        return instancia_id


class DecidirInstancia:
    """Aprovar (escolhendo a máquina), pôr em quarentena ou revogar."""

    def __init__(self, store: Any, audit: Any, transaction: Any) -> None:
        self.store, self.audit, self.transaction = store, audit, transaction

    def execute(self, *, instancia_id: str, acao: str, por: str, agora: datetime, maquina: str | None = None) -> dict[str, Any]:
        instancia = self.store.instancia(instancia_id)
        if instancia is None:
            raise LookupError("Instância não encontrada.")
        if acao == "aprovar" and maquina and not self.store.maquina_existe(maquina):
            raise TransicaoInvalida("Máquina não encontrada ou inativa.")
        antes = {"status": instancia.status, "machine_id": instancia.machine_id}
        novo = transicao(instancia.status, acao, maquina=maquina)
        instancia.status = novo
        if novo == APROVADA:
            instancia.machine_id, instancia.approved_at, instancia.approved_by = maquina, agora, por
        elif novo == QUARENTENA:
            instancia.quarantined_at = agora
        elif novo == REVOGADA:
            instancia.revoked_at = agora
            self.store.revogar_sessoes(instancia_id, agora)  # nenhuma rota responde a partir daqui
        _auditar(self.audit, ator_tipo="user", ator=por, acao=f"direto.instancia.{acao}", recurso=instancia_id, agora=agora,
                 antes=antes, depois={"status": novo, "machine_id": instancia.machine_id})
        self.transaction.commit()
        return {"id": instancia_id, "status": novo, "maquina_id": instancia.machine_id}


class PedirDesafio:
    def __init__(self, store: Any, transaction: Any) -> None:
        self.store, self.transaction = store, transaction

    def execute(self, *, instancia_id: str, agora: datetime) -> dict[str, Any]:
        instancia = self.store.instancia(instancia_id)
        if instancia is None or not pode_abrir_sessao(instancia.status):
            raise Recusado("instancia_inexistente_ou_revogada")
        desafio_id, nonce = f"dch_{uuid4().hex}", secrets.token_urlsafe(32)
        expira = agora + VALIDADE_DESAFIO
        self.store.adicionar_desafio(id=desafio_id, direct_instance_id=instancia_id, nonce=nonce, created_at=agora,
                                     expires_at=expira)
        self.transaction.commit()
        return {"desafio_id": desafio_id, "nonce": nonce, "expira_em": expira.isoformat()}


class AbrirSessao:
    def __init__(self, store: Any, audit: Any, transaction: Any, assinatura_confere: Callable[[str, bytes, str], bool]) -> None:
        self.store, self.audit, self.transaction, self.confere = store, audit, transaction, assinatura_confere

    def execute(self, *, instancia_id: str, desafio_id: str, assinatura: str, agora: datetime,
                ip: str | None = None) -> SessaoAberta:
        instancia = self.store.instancia(instancia_id)
        nonce = self.store.usar_desafio(desafio_id, instancia_id, agora) if instancia is not None else None
        motivo = None
        if instancia is None:
            motivo = "instancia_inexistente"
        elif not pode_abrir_sessao(instancia.status):
            motivo = "instancia_revogada"
        elif nonce is None:
            motivo = "desafio_invalido_vencido_ou_usado"
        elif not instancia.public_key or not self.confere(instancia.public_key, mensagem_assinada(instancia_id, desafio_id, nonce), assinatura):
            motivo = "assinatura_invalida"
        if motivo is not None:
            _auditar(self.audit, ator_tipo="direct_instance", ator=instancia_id, acao="direto.sessao.recusada",
                     recurso=instancia_id, agora=agora, metadados={"motivo": motivo, "ip": ip})
            self.transaction.commit()
            raise Recusado(motivo)
        token = f"dst_{secrets.token_urlsafe(32)}"
        expira = agora + DURACAO_SESSAO
        self.store.adicionar_sessao(id=f"dss_{uuid4().hex}", direct_instance_id=instancia_id, token_hash=hash_de(token),
                                    created_at=agora, expires_at=expira)
        instancia.last_seen_at = agora
        _auditar(self.audit, ator_tipo="direct_instance", ator=instancia_id, acao="direto.sessao.aberta", recurso=instancia_id,
                 agora=agora, metadados={"status": instancia.status, "ip": ip})
        self.transaction.commit()
        return SessaoAberta(token, expira, instancia_id, instancia.status)


class AutenticarSessao:
    def __init__(self, store: Any) -> None:
        self.store = store

    def execute(self, *, token: str | None, agora: datetime) -> InstanciaAutenticada:
        if not token:
            raise Recusado("sessao_ausente")
        achado = self.store.sessao(hash_de(token))
        if achado is None:
            raise Recusado("sessao_invalida")
        sessao, instancia = achado
        if sessao.revoked_at is not None:
            raise Recusado("sessao_revogada")
        if sessao.expires_at <= agora:
            raise Recusado("sessao_vencida")
        if not pode_abrir_sessao(instancia.status):
            raise Recusado("instancia_revogada")
        instancia.last_seen_at = agora
        return InstanciaAutenticada(instancia.id, instancia.automation_id, instancia.machine_id, instancia.status)
