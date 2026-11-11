"""ReceberDeclaracao: junta os campos, guarda o item e põe a tabela em prévia (Fase 8)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from modules.catalog.application.declaracao import ReceberDeclaracao
from modules.catalog.domain.formulario import Campo, Formulario, FormularioInvalido
from modules.catalog.domain.itens import Item

AGORA = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


class _Registro:
    def __init__(self, form: Formulario, item: dict | None = None, itens: dict[str, Item] | None = None) -> None:
        self.form, self.item, self.itens = form, item, itens or {}
        self.gravados: list[tuple] = []
        self.propostas: list[tuple] = []
        self.descartes = 0

    def formulario(self, automation_id):
        return self.form

    def item_da_automacao(self, automation_id):
        return self.item

    def gravar_formulario(self, automation_id, entrada, colunas, por, item=None):
        self.gravados.append((automation_id, entrada, colunas, por, item))
        return len(self.gravados)

    def todos(self, automation_id):
        return self.itens

    def spec(self, automation_id):
        dados = self.item or (self.gravados[-1][4] if self.gravados and self.gravados[-1][4] else None)
        return None if dados is None else SimpleNamespace(label=dados["nome"], key=dados["chave"],
                                                          group_attribute=dados["grupo"], attributes_schema={})

    def guardar_proposta(self, automation_id, linhas, resumo, instancia_id, agora):
        self.propostas.append((automation_id, linhas, resumo, instancia_id, agora))

    def descartar_proposta(self, automation_id):
        self.descartes += 1
        return True


def _receber(registro, bruto):
    audit: list = []
    saida = ReceberDeclaracao(registro, audit, agora=lambda: AGORA).execute(1, "dri_x", bruto)
    return saida, audit


COMPETENCIA = {"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano", "obrigatorio": True}


def test_primeira_declaracao_grava_e_audita() -> None:
    registro = _Registro(Formulario([], [], "manifesto"))
    saida, audit = _receber(registro, {"versao": "1.0", "parametros": [COMPETENCIA],
                                       "itens": {"nome": "Empresa", "chave": "codigo", "grupo": "matriz"}})
    assert saida["entrada"] == {"novos": ["competencia"], "fora_de_uso": [], "voltaram": []}
    assert saida["item"] == {"nome": "Empresa", "chave": "codigo", "grupo": "matriz"} and saida["tabela"] is None
    (_, entrada, colunas, por, item), = registro.gravados
    assert [(c.chave, c.origem) for c in entrada] == [("competencia", "automacao")] and colunas == []
    assert (por, item) == ("automacao:dri_x", saida["item"])
    (e,) = audit
    assert (e.action, e.actor_type, e.actor_id, e.resource_type, e.resource_id) == (
        "automacao.declarada", "direct_instance", "dri_x", "automation", "1")
    assert e.after["versao"] == 1 and e.after["versao_automacao"] == "1.0" and e.occurred_at == AGORA


def test_edicao_do_portal_vale_e_o_que_sumiu_fica_fora_de_uso() -> None:
    atual = [Campo("competencia", "Mês de referência", "mes_ano", origem="automacao"),
             Campo("modo", "Modo", "texto", origem="automacao"),
             Campo("obs", "Observação", "texto", origem="portal")]
    registro = _Registro(Formulario(atual, [], "portal"), item={"nome": "E", "chave": "c", "grupo": None})
    saida, audit = _receber(registro, {"parametros": [COMPETENCIA], "itens": {"nome": "Outro", "chave": "c"}})
    assert saida["entrada"] == {"novos": [], "fora_de_uso": ["modo"], "voltaram": []}
    assert saida["item"] is None  # item já definido: a declaração não troca
    entrada = registro.gravados[0][1]
    assert [(c.chave, c.rotulo, c.fora_de_uso) for c in entrada] == [
        ("competencia", "Mês de referência", False), ("modo", "Modo", True), ("obs", "Observação", False)]
    assert len(audit) == 1


def test_nada_mudou_nao_grava() -> None:
    atual = [Campo("competencia", "Competência", "mes_ano", obrigatorio=True, origem="automacao")]
    registro = _Registro(Formulario(atual, [], "portal"))
    saida, audit = _receber(registro, {"parametros": [COMPETENCIA]})
    assert registro.gravados == [] and audit == [] and not any(saida["entrada"].values())


def test_manifesto_sem_mudanca_passa_a_valer_o_portal() -> None:
    atual = [Campo("competencia", "Competência", "mes_ano", obrigatorio=True, origem="automacao")]
    registro = _Registro(Formulario(atual, [], "manifesto"))
    _receber(registro, {"parametros": [COMPETENCIA]})
    assert len(registro.gravados) == 1
    registro_vazio = _Registro(Formulario([], [], "manifesto"))
    _receber(registro_vazio, {})
    assert registro_vazio.gravados == []


def test_tabela_com_diferenca_vira_proposta() -> None:
    registro = _Registro(Formulario([], [], "portal"), item={"nome": "Empresa", "chave": "codigo", "grupo": None},
                         itens={"1": Item("1", "Um", None, {}, True)})
    tabela = [{"chave": "1", "rotulo": "Um"}, {"chave": "2", "rotulo": "Dois"}, {"chave": "x y", "rotulo": "?"}]
    saida, _ = _receber(registro, {"itens": {"nome": "Empresa", "chave": "codigo"}, "tabela": tabela})
    assert saida["tabela"] == {"novos": 1, "alterados": 0, "iguais": 1, "erros": 1}
    ((aid, linhas, resumo, inst, quando),) = registro.propostas
    assert (aid, linhas, resumo, inst, quando) == (1, tabela, saida["tabela"], "dri_x", AGORA)
    assert registro.descartes == 0


def test_tabela_igual_descarta_a_proposta() -> None:
    registro = _Registro(Formulario([], [], "portal"), item={"nome": "Empresa", "chave": "codigo", "grupo": None},
                         itens={"1": Item("1", "Um", None, {}, True)})
    saida, _ = _receber(registro, {"itens": {"nome": "Empresa", "chave": "codigo"}, "tabela": [{"chave": "1", "rotulo": "Um"}]})
    assert saida["tabela"] == {"novos": 0, "alterados": 0, "iguais": 1, "erros": 0}
    assert registro.propostas == [] and registro.descartes == 1


def test_declaracao_invalida_nao_grava_nada() -> None:
    registro = _Registro(Formulario([], [], "manifesto"))
    with pytest.raises(FormularioInvalido):
        _receber(registro, {"parametros": [{"chave": "A"}]})
    assert registro.gravados == [] and registro.propostas == []
