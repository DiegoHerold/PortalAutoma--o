"""As 11 regras de estimativa, uma por bloco. Os nomes dizem a regra."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules.telemetry.domain.estimativas import (
    AMOSTRAS,
    CONFIGURACAO_MUDOU,
    SEM_HISTORICO,
    Base,
    EstimativaEtapa,
    EtapaDeclarada,
    Medicao,
    duracao_liquida,
    estimar_etapa,
    execucoes_concluidas,
    somar,
)

T0 = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
AGORA = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
RUBRICAS = EtapaDeclarada("rubricas", "Rubricas", por_item=True, por_tarefa=True)
TROCAR = EtapaDeclarada("trocar_empresa", "Trocar empresa", por_item=True)
INICIAR = EtapaDeclarada("iniciar", "Iniciar", por_item=False)
ASS = "sep=1"


def m(execucao: str, segundos: float, *, item: str | None = "5066", etapa: str = "trocar_empresa", dia: int = 1,
      situacao: str = "ok", tarefas: int = 0, assinatura: str = ASS, automacao: int = 1, fim: datetime | None = None) -> Medicao:
    return Medicao(execucao, automacao, etapa, item, assinatura, situacao, tarefas, segundos,
                   fim if fim is not None else T0 + timedelta(days=dia))


# -- Regra 1: cada item tem o seu histórico --------------------------------------------

def test_regra_1_item_nunca_usa_historico_de_outro_item() -> None:
    historico = [m(f"e{i}", 100, item="5081", dia=i) for i in range(1, 6)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos is None
    assert estimativa.motivo == SEM_HISTORICO


def test_regra_1_outra_automacao_tambem_nao_serve() -> None:
    historico = [m("e1", 100, automacao=2)]
    assert estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA).segundos is None


# -- Regra 2: mediana das 5 últimas ----------------------------------------------------

def test_regra_2_mediana_das_5_ultimas_concluidas() -> None:
    # 7 execuções: as 2 mais antigas (1000 s) ficam fora; mediana de [10, 20, 30, 40, 900] = 30.
    tempos = [1000, 1000, 10, 20, 30, 40, 900]
    historico = [m(f"e{i}", s, dia=i) for i, s in enumerate(tempos, 1)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos == 30
    assert estimativa.base == Base("item", 5)
    assert AMOSTRAS == 5


def test_regra_2_mediana_nao_e_media() -> None:
    historico = [m("e1", 10, dia=1), m("e2", 20, dia=2), m("e3", 300, dia=3)]
    assert estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA).segundos == 20


def test_regra_2_com_menos_de_5_usa_as_que_existem() -> None:
    historico = [m("e1", 10, dia=1), m("e2", 30, dia=2)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos == 20
    assert estimativa.base == Base("item", 2)


# -- Regra 3: por tarefa ---------------------------------------------------------------

def test_regra_3_segundos_por_tarefa_vezes_tarefas_restantes() -> None:
    historico = [m("e1", 500, etapa="rubricas", tarefas=50, dia=1),   # 10 s/tarefa
                 m("e2", 600, etapa="rubricas", tarefas=50, dia=2),   # 12 s/tarefa
                 m("e3", 700, etapa="rubricas", tarefas=50, dia=3)]   # 14 s/tarefa
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=20)
    assert estimativa.segundos_por_tarefa == 12
    assert estimativa.segundos == 240
    assert estimativa.tarefas_restantes == 20
    assert estimativa.tarefas_origem == "declaradas"


def test_regra_3_retomada_so_conta_o_que_falta() -> None:
    historico = [m("e1", 500, etapa="rubricas", tarefas=50)]
    completa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=50)
    retomada = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=8)
    assert completa.segundos == 500
    assert retomada.segundos == 80


def test_regra_3_sem_tarefas_declaradas_usa_as_da_ultima_execucao_do_mesmo_item() -> None:
    historico = [m("e1", 300, etapa="rubricas", tarefas=30, dia=1),
                 m("e2", 400, etapa="rubricas", tarefas=40, dia=2),
                 m("x", 999, etapa="rubricas", tarefas=99, dia=3, item="5081")]
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA)
    assert estimativa.tarefas_restantes == 40
    assert estimativa.tarefas_origem == "ultima_execucao"
    assert estimativa.segundos == 400


def test_regra_3_nada_restante_estima_zero() -> None:
    historico = [m("e1", 500, etapa="rubricas", tarefas=50)]
    assert estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=0).segundos == 0
    assert estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=-3).segundos == 0


def test_regra_3_execucoes_sem_tarefa_nao_entram_na_taxa() -> None:
    historico = [m("e1", 500, etapa="rubricas", tarefas=0, dia=1), m("e2", 100, etapa="rubricas", tarefas=10, dia=2)]
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=1)
    assert estimativa.segundos_por_tarefa == 10
    assert estimativa.base == Base("item", 1)


def test_regra_3_so_execucoes_sem_tarefa_nao_tem_base() -> None:
    historico = [m("e1", 500, etapa="rubricas", tarefas=0)]
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=5)
    assert estimativa.segundos is None and estimativa.motivo == SEM_HISTORICO


# -- Regra 4: erro e interrompida não são base -----------------------------------------

@pytest.mark.parametrize("situacao", ["erro", "interrompida", "executando"])
def test_regra_4_etapa_que_nao_terminou_ok_nao_e_base(situacao: str) -> None:
    historico = [m("e1", 10, dia=1), m("e2", 5000, dia=2, situacao=situacao)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos == 10
    assert estimativa.base == Base("item", 1)


def test_regra_4_ultima_parte_com_erro_tira_a_execucao_inteira_da_base() -> None:
    historico = [m("e1", 100, dia=1, situacao="ok"), m("e1", 50, dia=2, situacao="erro"), m("e2", 30, dia=3)]
    concluidas = execucoes_concluidas(historico)
    assert [s for _, s, _ in concluidas] == [30]


@pytest.mark.parametrize("situacao", ["erro", "interrompida"])
def test_decisao_7_retomada_que_concluiu_soma_a_parte_que_falhou(situacao: str) -> None:
    historico = [m("e1", 50, etapa="rubricas", tarefas=30, dia=1, situacao=situacao),
                 m("e1", 40, etapa="rubricas", tarefas=20, dia=2, situacao="ok")]
    assert execucoes_concluidas(historico) == [(T0 + timedelta(days=2), 90, 50)]


def test_decisao_7_parte_ainda_aberta_tira_a_execucao() -> None:
    aberta = Medicao("e1", 1, "trocar_empresa", "5066", ASS, "executando", 0, 10, None)
    assert execucoes_concluidas([m("e1", 10, dia=1), aberta]) == []


def test_decisao_7_partes_ok_da_mesma_execucao_somam_numa_so() -> None:
    historico = [m("e1", 100, etapa="rubricas", tarefas=30, dia=1), m("e1", 60, etapa="rubricas", tarefas=20, dia=2)]
    concluidas = execucoes_concluidas(historico)
    assert concluidas == [(T0 + timedelta(days=2), 160, 50)]
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=10)
    assert estimativa.base == Base("item", 1)
    assert estimativa.segundos == pytest.approx(32)


def test_ordem_mais_recente_primeiro() -> None:
    historico = [m("velha", 1, dia=1), m("nova", 2, dia=3), m("meio", 3, dia=2)]
    assert [s for _, s, _ in execucoes_concluidas(historico)] == [2, 3, 1]


# -- Regra 5: etapa sem item usa todas as execuções da automação -------------------------

def test_regra_5_etapa_sem_item_usa_a_automacao_toda() -> None:
    historico = [m("e1", 20, etapa="iniciar", item=None, dia=1, assinatura=""),
                 m("e2", 30, etapa="iniciar", item=None, dia=2, assinatura="outra"),
                 m("e3", 40, etapa="iniciar", item="qualquer", dia=3)]
    estimativa = estimar_etapa(INICIAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos == 30
    assert estimativa.base == Base("automacao", 3)
    assert estimativa.item is None


# -- Regra 6: configuração que muda o trabalho zera a base --------------------------------

def test_regra_6_mudou_a_configuracao_zera_a_base_com_motivo() -> None:
    historico = [m(f"e{i}", 100, dia=i, assinatura="sep=0") for i in range(1, 4)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", "sep=1", historico, AGORA)
    assert estimativa.segundos is None
    assert estimativa.motivo == CONFIGURACAO_MUDOU


def test_regra_6_so_usa_execucoes_com_a_configuracao_atual() -> None:
    historico = [m("e1", 100, dia=1, assinatura="sep=0"), m("e2", 20, dia=2, assinatura="sep=1")]
    estimativa = estimar_etapa(TROCAR, 1, "5066", "sep=1", historico, AGORA)
    assert estimativa.segundos == 20
    assert estimativa.base == Base("item", 1)


def test_regra_6_configuracao_antiga_que_nunca_concluiu_e_sem_historico() -> None:
    historico = [m("e1", 100, assinatura="sep=0", situacao="erro")]
    assert estimar_etapa(TROCAR, 1, "5066", "sep=1", historico, AGORA).motivo == SEM_HISTORICO


# -- Regra 7: pausas fora da duração ----------------------------------------------------

def test_regra_7_pausa_dentro_da_etapa_e_descontada() -> None:
    inicio, fim = T0, T0 + timedelta(minutes=10)
    liquida, pausa = duracao_liquida(inicio, fim, [(T0 + timedelta(minutes=2), T0 + timedelta(minutes=3))])
    assert (liquida, pausa) == (540, 60)


def test_regra_7_so_conta_a_parte_da_pausa_dentro_da_etapa() -> None:
    inicio, fim = T0 + timedelta(minutes=5), T0 + timedelta(minutes=10)
    pausas = [(T0, T0 + timedelta(minutes=6)), (T0 + timedelta(minutes=9), T0 + timedelta(minutes=20))]
    assert duracao_liquida(inicio, fim, pausas) == (180, 120)


def test_regra_7_pausas_sobrepostas_nao_descontam_duas_vezes() -> None:
    pausas = [(T0 + timedelta(minutes=1), T0 + timedelta(minutes=4)),
              (T0 + timedelta(minutes=2), T0 + timedelta(minutes=3)),
              (T0 + timedelta(minutes=3), T0 + timedelta(minutes=5)),
              (T0 + timedelta(minutes=7), T0 + timedelta(minutes=8))]
    assert duracao_liquida(T0, T0 + timedelta(minutes=10), pausas) == (300, 300)


def test_regra_7_pausa_aberta_vai_ate_o_fim() -> None:
    assert duracao_liquida(T0, T0 + timedelta(minutes=10), [(T0 + timedelta(minutes=8), None)]) == (480, 120)


def test_regra_7_pausa_fora_da_etapa_e_ignorada() -> None:
    pausas = [(T0 - timedelta(minutes=5), T0 - timedelta(minutes=1)), (T0 + timedelta(minutes=11), T0 + timedelta(minutes=12))]
    assert duracao_liquida(T0, T0 + timedelta(minutes=10), pausas) == (600, 0)


def test_regra_7_sem_pausa_e_fim_antes_do_inicio() -> None:
    assert duracao_liquida(T0, T0 + timedelta(seconds=90), []) == (90, 0)
    assert duracao_liquida(T0, T0 - timedelta(seconds=5), []) == (0, 0)


# -- Regra 8: só o que veio antes -------------------------------------------------------

def test_regra_8_so_entra_o_que_terminou_antes_do_corte() -> None:
    corte = T0 + timedelta(days=3)
    historico = [m("e1", 10, dia=1), m("e2", 20, dia=2), m("e3", 999, fim=corte), m("e4", 999, dia=5)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, corte)
    assert estimativa.segundos == 15
    assert estimativa.base == Base("item", 2)


def test_regra_8_a_propria_execucao_nunca_e_base() -> None:
    historico = [m("atual", 999, dia=1), m("e2", 20, dia=2)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA, execucao_atual="atual")
    assert estimativa.segundos == 20


def test_regra_8_medicao_sem_fim_nao_e_base() -> None:
    aberta = Medicao("e1", 1, "trocar_empresa", "5066", ASS, "ok", 0, 10, None)
    assert estimar_etapa(TROCAR, 1, "5066", ASS, [aberta], AGORA).segundos is None


# -- Regra 9: sem base, sem número -------------------------------------------------------

def test_regra_9_item_novo_sem_historico() -> None:
    estimativa = estimar_etapa(TROCAR, 1, "9999", ASS, [], AGORA)
    assert (estimativa.segundos, estimativa.base, estimativa.motivo) == (None, None, SEM_HISTORICO)


def test_regra_9_sem_base_fica_fora_da_soma_e_e_contada() -> None:
    soma = somar([EstimativaEtapa("a", "1", 100, Base("item", 5)), EstimativaEtapa("b", "1", None, None, SEM_HISTORICO),
                  EstimativaEtapa("c", "1", 50, Base("item", 2))])
    assert (soma.segundos, soma.sem_base, soma.total, soma.completa) == (150, 1, 3, False)


def test_regra_9_tudo_sem_base_soma_none_e_nao_zero() -> None:
    soma = somar([EstimativaEtapa("a", "1", None, None, SEM_HISTORICO)])
    assert soma.segundos is None
    assert soma.completa is False


# -- Regra 10: job = soma das etapas, execução = soma dos jobs -----------------------------

def test_regra_10_job_e_execucao_somam() -> None:
    job_a = somar([EstimativaEtapa("a", "1", 100, Base("item", 5)), EstimativaEtapa("b", "1", 20, Base("item", 5))])
    job_b = somar([EstimativaEtapa("a", "2", 30, Base("item", 1)), EstimativaEtapa("b", "2", None, None, SEM_HISTORICO)])
    execucao = somar([job_a, job_b])
    assert job_a.completa and job_a.segundos == 120
    assert (execucao.segundos, execucao.sem_base, execucao.total) == (150, 1, 4)


def test_regra_10_job_sem_nenhuma_base_conta_as_etapas_dele() -> None:
    vazio = somar([EstimativaEtapa("a", "1", None, None, SEM_HISTORICO), EstimativaEtapa("b", "1", None, None, SEM_HISTORICO)])
    execucao = somar([vazio, somar([EstimativaEtapa("a", "2", 10, Base("item", 1))])])
    assert (execucao.segundos, execucao.sem_base, execucao.total) == (10, 2, 3)


def test_regra_10_soma_zero_e_numero() -> None:
    assert somar([EstimativaEtapa("a", "1", 0, Base("item", 1))]).segundos == 0
    assert somar([EstimativaEtapa("a", "1", 0, Base("item", 1))]).completa is True


# -- Regra 11: toda estimativa diz de onde veio --------------------------------------------

def test_regra_11_base_descreve_a_origem() -> None:
    assert Base("item", 5).texto() == "últimas 5 execuções do item"
    assert Base("automacao", 3).texto() == "últimas 3 execuções da automação"
    assert Base("item", 1).texto() == "última execução do item"


def test_regra_11_estimativa_com_numero_sempre_tem_base() -> None:
    historico = [m("e1", 10)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA)
    assert estimativa.segundos is not None and estimativa.base is not None and estimativa.motivo is None


# -- Casos de borda apontados pelo teste de mutação -------------------------------------
# Chaves montadas em tempo de execução: literais iguais são o mesmo objeto no CPython, e
# um "is" trocado por "==" passaria despercebido. No Portal as chaves vêm do banco.

def _texto(*partes: str) -> str:
    return "".join(partes)


def test_borda_item_com_chave_menor_nao_serve_de_base() -> None:
    historico = [m("e1", 100, item="5000")]
    assert estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA).segundos is None


def test_borda_chaves_iguais_vindas_do_banco_sao_o_mesmo_item() -> None:
    historico = [m("e1", 40, item=_texto("50", "66"), etapa=_texto("trocar", "_empresa"), assinatura=_texto("sep", "=1"))]
    estimativa = estimar_etapa(TROCAR, 1, str(5066), _texto("sep=", "1"), historico, AGORA,
                               execucao_atual=_texto("outra", "-execucao"))
    assert estimativa.segundos == 40


def test_borda_automacao_com_id_menor_nao_serve_de_base() -> None:
    historico = [m("e1", 100, automacao=7)]
    assert estimar_etapa(TROCAR, 8, "5066", ASS, historico, AGORA).segundos is None


def test_borda_ids_grandes_de_automacao_iguais_valem() -> None:
    historico = [m("e1", 30, automacao=int("100000"))]
    assert estimar_etapa(TROCAR, int("100000"), "5066", ASS, historico, AGORA).segundos == 30


@pytest.mark.parametrize("outra", ["a_antes", "z_depois"])
def test_borda_outra_etapa_nao_serve_de_base(outra: str) -> None:
    historico = [m("e1", 100, etapa=outra)]
    assert estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA).segundos is None


def test_borda_configuracao_maior_tambem_nao_serve() -> None:
    historico = [m("e1", 100, assinatura="sep=1")]
    estimativa = estimar_etapa(TROCAR, 1, "5066", "sep=0", historico, AGORA)
    assert estimativa.motivo == CONFIGURACAO_MUDOU


def test_borda_execucao_atual_igual_vinda_do_banco_e_excluida() -> None:
    historico = [m(_texto("ex", "ec-1"), 999, dia=1), m("e2", 20, dia=2)]
    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, historico, AGORA, execucao_atual=_texto("exec", "-1"))
    assert estimativa.segundos == 20


def test_borda_execucao_com_uma_tarefa_entra_na_taxa() -> None:
    historico = [m("e1", 12, etapa="rubricas", tarefas=1)]
    estimativa = estimar_etapa(RUBRICAS, 1, "5066", ASS, historico, AGORA, tarefas_restantes=3)
    assert estimativa.segundos_por_tarefa == 12
    assert estimativa.segundos == 36


def test_borda_pausa_vazia_antes_de_uma_valida_nao_interrompe_o_desconto() -> None:
    pausas = [(T0 + timedelta(minutes=1), T0 + timedelta(minutes=1)),   # vazia
              (T0 + timedelta(minutes=5), T0 + timedelta(minutes=6))]
    assert duracao_liquida(T0, T0 + timedelta(minutes=10), pausas) == (540, 60)


def test_borda_etapa_e_por_item_por_padrao_e_nao_por_tarefa() -> None:
    etapa = EtapaDeclarada("trocar_empresa", "Trocar empresa")
    assert (etapa.por_item, etapa.por_tarefa) == (True, False)
    historico = [m("e1", 10, item="5081")]
    assert estimar_etapa(etapa, 1, "5066", ASS, historico, AGORA).segundos is None


def test_borda_pausa_contida_em_outra_nao_encurta_a_maior() -> None:
    pausas = [(T0 + timedelta(minutes=1), T0 + timedelta(minutes=4)),
              (T0 + timedelta(minutes=2), T0 + timedelta(minutes=3))]
    assert duracao_liquida(T0, T0 + timedelta(minutes=10), pausas) == (420, 180)


def test_borda_estimativas_sao_imutaveis() -> None:
    import dataclasses

    estimativa = estimar_etapa(TROCAR, 1, "5066", ASS, [m("e1", 10)], AGORA)
    with pytest.raises(dataclasses.FrozenInstanceError):
        estimativa.segundos = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Base("item", 1).amostras = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        TROCAR.por_item = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        m("e1", 1).duracao_s = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        somar([]).segundos = 1  # type: ignore[misc]


def test_borda_soma_vazia() -> None:
    soma = somar([])
    assert (soma.segundos, soma.sem_base, soma.total, soma.completa) == (None, 0, 0, False)


def test_borda_situacao_ok_vinda_do_banco_vale() -> None:
    historico = [m("e1", 25, situacao=_texto("o", "k"))]
    assert execucoes_concluidas(historico) == [(T0 + timedelta(days=1), 25, 0)]


def test_borda_execucao_aberta_nao_tira_as_outras() -> None:
    aberta = Medicao("aberta", 1, "trocar_empresa", "5066", ASS, "executando", 0, 10, None)
    historico = [aberta, m("concluida", 30, dia=2), m("com_erro", 99, dia=3, situacao="erro"), m("outra", 50, dia=4)]
    assert [s for _, s, _ in execucoes_concluidas(historico)] == [50, 30]
