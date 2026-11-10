"""Instância direta (ADR-018): estados, transições e validades da inscrição e da sessão.

Desenho aprovado na seção 7 da Fase 0. Regras puras; a assinatura é conferida na
infraestrutura (``cryptography``).
"""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta

PENDENTE = "pendente"
APROVADA = "aprovada"
QUARENTENA = "quarentena"
REVOGADA = "revogada"
ESTADOS = (PENDENTE, APROVADA, QUARENTENA, REVOGADA)

VALIDADE_CODIGO = timedelta(minutes=30)
VALIDADE_DESAFIO = timedelta(seconds=60)
DURACAO_SESSAO = timedelta(minutes=10)

# O que a instância assina: amarra o desafio à instância e à versão do protocolo.
PROTOCOLO = "portal-automacoes/direto/1"
FORMATO_CODIGO = re.compile(r"[A-Z0-9]{4}(-[A-Z0-9]{4}){3}")


class TransicaoInvalida(ValueError):
    pass


# Quem pode ir para onde. Revogada é final: para voltar, inscreve de novo.
TRANSICOES = {
    "aprovar": {PENDENTE, QUARENTENA},
    "quarentena": {APROVADA},
    "revogar": {PENDENTE, APROVADA, QUARENTENA},
}
DESTINO = {"aprovar": APROVADA, "quarentena": QUARENTENA, "revogar": REVOGADA}


def transicao(atual: str, acao: str, *, maquina: str | None = None) -> str:
    if acao not in TRANSICOES:
        raise TransicaoInvalida(f"Ação desconhecida: {acao}.")
    if atual not in TRANSICOES[acao]:
        raise TransicaoInvalida(f"Instância {atual} não pode receber '{acao}'.")
    if acao == "aprovar" and not maquina:
        raise TransicaoInvalida("Para aprovar, escolha a máquina onde a instância roda.")
    return DESTINO[acao]


def pode_abrir_sessao(estado: str) -> bool:
    """Pendente abre sessão para saber que ainda espera aprovação; revogada nunca."""
    return estado in (PENDENTE, APROVADA, QUARENTENA)


def pode_receber_jobs(estado: str) -> bool:
    """Quarentena conecta e termina o job atual, mas não recebe novos (Fase 3)."""
    return estado == APROVADA


def mensagem_assinada(instancia_id: str, desafio_id: str, nonce: str) -> bytes:
    return f"{PROTOCOLO}|{instancia_id}|{desafio_id}|{nonce}".encode("utf-8")


def normalizar_codigo(codigo: str) -> str | None:
    """Aceita com ou sem hífens, maiúsculo ou não. None se o formato não bate."""
    limpo = re.sub(r"[^A-Za-z0-9]", "", codigo or "").upper()
    if len(limpo) != 16:
        return None
    formatado = "-".join(limpo[i:i + 4] for i in range(0, 16, 4))
    return formatado if FORMATO_CODIGO.fullmatch(formatado) else None


def hash_de(segredo: str) -> str:
    return hashlib.sha256(segredo.encode("utf-8")).hexdigest()
