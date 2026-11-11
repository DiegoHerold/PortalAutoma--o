"""Manifesto: modo de execução obrigatório (decisão 10), itens, etapas e regras de repetição."""

from __future__ import annotations

import json
from typing import Any

import pytest

from modules.catalog.domain.manifest import parse_automation_manifest

BASE: dict[str, Any] = {
    "schema_version": "1.0",
    "automation": {"id": "dominio.integracao_contabil", "name": "Integração Contábil", "version": "2.0.0"},
    "runtime": {"id": "python-desktop", "version": "3.12"},
    "entrypoint": {"type": "python-module", "module": "dominio_folha.cli"},
    "execution": {"mode": "tela", "timeout_seconds": 14400},
    "itens": {
        "nome": "Empresa",
        "chave": "codigo",
        "rotulo": "nome",
        "grupo": "matriz_codigo",
        "atributos": {
            "type": "object",
            "properties": {
                "codigo": {"type": "integer"},
                "nome": {"type": "string"},
                "matriz_codigo": {"type": ["integer", "null"]},
                "separar_por_custo": {"type": "boolean"},
                "rubricas_ignoradas": {"type": "array", "items": {"type": "integer"}},
            },
        },
        "afetam_trabalho": ["separar_por_custo"],
    },
    "etapas": [
        {"chave": "iniciar", "nome": "Iniciar", "por_item": False},
        {"chave": "trocar_empresa", "nome": "Trocar empresa"},
        {"chave": "rubricas", "nome": "Rubricas", "por_tarefa": True},
        {"chave": "txt", "nome": "Integração (TXT)", "por_tarefa": True},
        {"chave": "aviso", "nome": "Aviso", "por_item": False},
    ],
}


def _parse(**alteracoes: Any):
    dados = json.loads(json.dumps(BASE))
    for chave, valor in alteracoes.items():
        if valor is None:
            dados.pop(chave, None)
        else:
            dados[chave] = valor
    return parse_automation_manifest(json.dumps(dados))


def _codigos(resultado) -> set[str]:
    return {issue.code for issue in resultado.issues}


def test_manifesto_completo_da_integracao_contabil() -> None:
    manifesto, resultado = _parse()
    assert resultado.is_valid, resultado.errors
    assert manifesto.execution.mode == "interactive"
    assert manifesto.items.label == "Empresa"
    assert manifesto.items.group_attribute == "matriz_codigo"
    assert manifesto.items.work_attributes == ("separar_por_custo",)
    assert [s.key for s in manifesto.steps] == ["iniciar", "trocar_empresa", "rubricas", "txt", "aviso"]
    assert [s.per_item for s in manifesto.steps] == [False, True, True, True, False]
    assert [s.per_task for s in manifesto.steps] == [False, False, True, True, False]
    assert manifesto.normalized["steps"][2] == {"key": "rubricas", "name": "Rubricas", "per_item": True, "per_task": True}
    assert manifesto.normalized["items"]["work_attributes"] == ["separar_por_custo"]


def test_modo_de_execucao_e_obrigatorio() -> None:
    _, resultado = _parse(execution={"timeout_seconds": 60})
    assert "MANIFEST_EXECUTION_MODE_REQUIRED" in _codigos(resultado)


@pytest.mark.parametrize("modo,pool", [("tela", "interactive"), ("navegador", "browser"), ("segundo_plano", "background"),
                                       ("interactive", "interactive"), ("browser", "browser"), ("background", "background")])
def test_modo_aceita_portugues_e_nome_do_pool(modo: str, pool: str) -> None:
    manifesto, resultado = _parse(execution={"mode": modo})
    assert resultado.is_valid, resultado.errors
    assert manifesto.execution.mode == pool


def test_forma_antiga_de_declarar_tela_continua_valendo() -> None:
    manifesto, resultado = _parse(execution={"interactive_session": True})
    assert resultado.is_valid and manifesto.execution.mode == "interactive"


def test_modo_desconhecido_e_recusado() -> None:
    _, resultado = _parse(execution={"mode": "magico"})
    assert "MANIFEST_EXECUTION_MODE_UNSUPPORTED" in _codigos(resultado)


def test_tela_nao_repete_sozinha_por_padrao() -> None:
    manifesto, _ = _parse()
    assert manifesto.execution.safe_to_retry is False
    assert manifesto.execution.central_state is False
    manifesto, _ = _parse(execution={"mode": "tela", "seguro_repetir": True, "estado_central": True})
    assert manifesto.execution.safe_to_retry is True and manifesto.execution.central_state is True


def test_flag_que_nao_e_booleana_e_recusada() -> None:
    _, resultado = _parse(execution={"mode": "tela", "seguro_repetir": "sim"})
    assert "MANIFEST_EXECUTION_FLAG_INVALID" in _codigos(resultado)


def test_automacao_simples_sem_itens_nem_etapas() -> None:
    manifesto, resultado = _parse(itens=None, etapas=None)
    assert resultado.is_valid
    assert manifesto.items is None and manifesto.steps == ()


def test_etapa_repetida_e_recusada() -> None:
    _, resultado = _parse(etapas=[{"chave": "txt"}, {"chave": "txt"}])
    assert "MANIFEST_STEP_DUPLICATED" in _codigos(resultado)


@pytest.mark.parametrize("etapa", [{"chave": "trocar empresa"}, {"nome": "sem chave"}, {"chave": "x", "por_tarefa": "sim"}, "rubricas"])
def test_etapa_invalida_e_recusada(etapa: Any) -> None:
    _, resultado = _parse(etapas=[etapa])
    assert not resultado.is_valid


def test_etapa_sem_nome_usa_a_chave() -> None:
    manifesto, _ = _parse(etapas=[{"chave": "txt"}])
    assert manifesto.steps[0].name == "txt"


def test_atributo_que_afeta_o_trabalho_precisa_estar_declarado() -> None:
    itens = {**BASE["itens"], "afetam_trabalho": ["centro_de_custo"]}
    _, resultado = _parse(itens=itens)
    assert "MANIFEST_ITEMS_ATTRIBUTE_UNKNOWN" in _codigos(resultado)


def test_item_sem_nome_ou_chave_e_recusado() -> None:
    _, resultado = _parse(itens={"chave": "codigo"})
    assert "MANIFEST_ITEMS_LABEL_REQUIRED" in _codigos(resultado)
    _, resultado = _parse(itens={"nome": "Empresa"})
    assert "MANIFEST_ITEMS_KEY_REQUIRED" in _codigos(resultado)


def test_mudar_as_etapas_muda_o_hash_do_manifesto() -> None:
    a, _ = _parse()
    b, _ = _parse(etapas=[{"chave": "iniciar", "por_item": False}])
    assert a.content_hash != b.content_hash
