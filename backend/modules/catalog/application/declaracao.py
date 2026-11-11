"""Receber a declaração da automação ao conectar (Fase 8).

Campos: junta com o que está no Portal (só acrescenta; ver ``formulario.juntar``), grava se
mudou e audita. Item: se o manifesto não define, vale o que a automação declarou. Tabela:
vira uma prévia na aba Itens, para alguém aprovar; sem diferença, não fica nada pendente.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.catalog.domain.declaracao import validar_declaracao
from modules.catalog.domain.formulario import juntar
from modules.catalog.domain.itens import previa
from modules.governance.domain.audit import AuditEvent


class ReceberDeclaracao:
    def __init__(self, registro: Any, audit: Any, agora: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.registro = registro
        self.audit = audit
        self.agora = agora

    def execute(self, automation_id: int, instancia_id: str | None, bruto: Any) -> dict[str, Any]:
        declaracao = validar_declaracao(bruto)
        atual = self.registro.formulario(automation_id)
        entrada, mudou_entrada = juntar(atual.entrada, declaracao.parametros)
        colunas, mudou_colunas = juntar(atual.colunas, declaracao.colunas)
        item_atual = self.registro.item_da_automacao(automation_id)
        item_novo = None
        if declaracao.item is not None and item_atual is None:
            item_novo = {"nome": declaracao.item.nome, "chave": declaracao.item.chave, "grupo": declaracao.item.grupo}
        mudou = any(mudou_entrada.values()) or any(mudou_colunas.values()) or item_novo is not None
        # Primeira declaração com os campos ainda vindos do manifesto: passa a valer o Portal.
        if mudou or (atual.origem == "manifesto" and (declaracao.parametros or declaracao.colunas)):
            versao = self.registro.gravar_formulario(automation_id, entrada, colunas, f"automacao:{instancia_id}", item_novo)
            self.audit.append(AuditEvent(
                id=f"aud_{uuid4().hex}", actor_type="direct_instance", actor_id=instancia_id,
                action="automacao.declarada", resource_type="automation", resource_id=str(automation_id),
                before={"entrada": [c.chave for c in atual.entrada], "colunas": [c.chave for c in atual.colunas]},
                after={"versao": versao, "entrada": mudou_entrada, "colunas": mudou_colunas,
                       "versao_automacao": declaracao.versao, "item": item_novo},
                occurred_at=self.agora()))
        tabela = None
        if declaracao.tabela is not None:
            resultado = previa(self.registro.todos(automation_id), declaracao.tabela, self.registro.spec(automation_id))
            tabela = {"novos": len(resultado["novos"]), "alterados": len(resultado["alterados"]),
                      "iguais": resultado["iguais"], "erros": len(resultado["erros"])}
            if resultado["novos"] or resultado["alterados"] or resultado["erros"]:
                self.registro.guardar_proposta(automation_id, declaracao.tabela, tabela, instancia_id, self.agora())
            else:
                self.registro.descartar_proposta(automation_id)  # já está igual: nada a aprovar
        return {"entrada": mudou_entrada, "colunas": mudou_colunas, "item": item_novo, "tabela": tabela}
