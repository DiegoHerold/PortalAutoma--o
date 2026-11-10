"""Instância direta: transições, código de inscrição e mensagem assinada (regras puras)."""

from __future__ import annotations

import pytest

from modules.fleet.domain.instancia_direta import (
    APROVADA,
    PENDENTE,
    QUARENTENA,
    REVOGADA,
    TransicaoInvalida,
    hash_de,
    mensagem_assinada,
    normalizar_codigo,
    pode_abrir_sessao,
    pode_receber_jobs,
    transicao,
)


@pytest.mark.parametrize("atual,acao,destino", [
    (PENDENTE, "aprovar", APROVADA),
    (QUARENTENA, "aprovar", APROVADA),
    (APROVADA, "quarentena", QUARENTENA),
    (PENDENTE, "revogar", REVOGADA),
    (APROVADA, "revogar", REVOGADA),
    (QUARENTENA, "revogar", REVOGADA),
])
def test_transicoes_permitidas(atual: str, acao: str, destino: str) -> None:
    assert transicao(atual, acao, maquina="mch_1") == destino


@pytest.mark.parametrize("atual,acao", [
    (APROVADA, "aprovar"), (REVOGADA, "aprovar"), (PENDENTE, "quarentena"), (QUARENTENA, "quarentena"),
    (REVOGADA, "quarentena"), (REVOGADA, "revogar"),
])
def test_transicoes_proibidas(atual: str, acao: str) -> None:
    with pytest.raises(TransicaoInvalida):
        transicao(atual, acao, maquina="mch_1")


def test_aprovar_exige_maquina_e_acao_desconhecida_e_recusada() -> None:
    with pytest.raises(TransicaoInvalida, match="máquina"):
        transicao(PENDENTE, "aprovar", maquina=None)
    with pytest.raises(TransicaoInvalida, match="desconhecida"):
        transicao(PENDENTE, "apagar")


def test_quem_abre_sessao_e_quem_recebe_job() -> None:
    assert [e for e in (PENDENTE, APROVADA, QUARENTENA, REVOGADA) if pode_abrir_sessao(e)] == [PENDENTE, APROVADA, QUARENTENA]
    assert [e for e in (PENDENTE, APROVADA, QUARENTENA, REVOGADA) if pode_receber_jobs(e)] == [APROVADA]
    assert not pode_receber_jobs("qualquer")


@pytest.mark.parametrize("digitado,esperado", [
    ("ABCD-EFGH-JKLM-NPQR", "ABCD-EFGH-JKLM-NPQR"),
    ("abcd efgh jklm npqr", "ABCD-EFGH-JKLM-NPQR"),
    ("abcdefghjklmnpqr", "ABCD-EFGH-JKLM-NPQR"),
    ("ABCD-EFGH-JKLM", None),
    ("ABCD-EFGH-JKLM-NPQR-STUV", None),
    ("", None),
])
def test_codigo_normalizado(digitado: str, esperado: str | None) -> None:
    assert normalizar_codigo(digitado) == esperado


def test_mensagem_assinada_amarra_instancia_desafio_e_protocolo() -> None:
    assert mensagem_assinada("dri_1", "dch_2", "n3") == b"portal-automacoes/direto/1|dri_1|dch_2|n3"
    assert mensagem_assinada("dri_1", "dch_2", "n3") != mensagem_assinada("dri_9", "dch_2", "n3")
    assert hash_de("x") == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"


def test_validades_aprovadas_na_fase_0() -> None:
    from datetime import timedelta

    from modules.fleet.domain.instancia_direta import DURACAO_SESSAO, VALIDADE_CODIGO, VALIDADE_DESAFIO

    assert (VALIDADE_CODIGO, VALIDADE_DESAFIO, DURACAO_SESSAO) == (
        timedelta(minutes=30), timedelta(seconds=60), timedelta(minutes=10))


def test_so_aprovar_exige_maquina_e_textos_vindos_de_fora() -> None:
    def de_fora(texto: str) -> str:  # como chega da requisição: não é o mesmo objeto do literal
        return "".join(list(texto))

    assert transicao(de_fora(APROVADA), de_fora("quarentena"), maquina=None) == QUARENTENA
    assert transicao(de_fora(PENDENTE), de_fora("revogar"), maquina=None) == REVOGADA
    with pytest.raises(TransicaoInvalida):
        transicao(de_fora(PENDENTE), de_fora("aprovar"), maquina=None)
    assert pode_receber_jobs(de_fora(APROVADA)) and not pode_receber_jobs("") and not pode_receber_jobs("a")
