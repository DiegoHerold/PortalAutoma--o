"""Entrega do job à instância direta (ADR-018; antecipado da Fase 6).

O despacho (Fase 3) já reservou o job para a instância: criou a tentativa ``committed`` e
tomou a trava de tela da máquina. Aqui a instância, com a sessão aberta, pede o próximo
job e recebe o token só daquele job. Enquanto a automação não mandou nenhum evento,
pedir de novo troca o token (o anterior é revogado), para uma instância que reiniciou.
Depois do primeiro evento, ninguém recebe o mesmo job de novo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


class EntregarProximoJob:
    def __init__(self, reader: Any, emitir_token: Callable[..., str], transaction: Any) -> None:
        self.reader = reader
        self.emitir_token = emitir_token
        self.transaction = transaction

    def execute(self, *, instancia_id: str, agora: datetime) -> dict[str, Any] | None:
        pendente = self.reader.tentativa_pendente(instancia_id)
        if pendente is None:
            return None
        self.reader.revogar_tokens(pendente["attempt_id"], agora)
        token = self.emitir_token(task_execution_id=pendente["job_id"], execution_attempt_id=pendente["attempt_id"],
                                  direct_instance_id=instancia_id, now=agora)
        self.transaction.commit()
        return {
            "job_id": pendente["job_id"],
            "execucao_id": pendente["execution_id"],
            "tentativa": pendente["attempt_number"],
            "token": token,
            "parametros": pendente["parametros"],
            "itens": pendente["itens"],
        }
