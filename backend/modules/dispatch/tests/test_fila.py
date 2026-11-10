"""Regras da fila (domínio puro). Nomes dizem a regra ou o cenário obrigatório."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from modules.dispatch.domain.fila import (
    ACIMA_DA_ESTIMATIVA,
    AGUARDANDO_SEM_PREVISAO,
    JOB_PERDIDO_NA_MAQUINA,
    MAQUINA_SEM_SINAL,
    SEM_HISTORICO,
    SEM_MAQUINA_COMPATIVEL,
    SESSAO_BLOQUEADA,
    TELA,
    EmExecucao,
    JobNaFila,
    Maquina,
    agrupar,
    chave_de_duplicata,
    disponivel,
    maquina_da_retomada,
    ordenar,
    pode_repetir_sozinho,
    prever,
    proximo_job,
    vagas_livres,
)

AGORA = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
DUAS = frozenset({"A", "B"})


def job(id: str, estimativa: float | None = 60, *, pool: str = TELA, prioridade: int = 0, lote: str = "L1",
        chegada: int = 0, maquinas: frozenset[str] = DUAS, posicao: int | None = None, obrigatoria: str | None = None,
        motivos: tuple[str, ...] = ()) -> JobNaFila:
    return JobNaFila(id, pool, prioridade, lote, AGORA + timedelta(seconds=chegada), estimativa, maquinas, posicao,
                     obrigatoria, motivos)


def maquina(id: str, *, online: bool = True, tela: int = 1, fundo: int = 0, rodando: tuple = (),
            bloqueada: bool = False, perdido: bool = False) -> Maquina:
    return Maquina(id, online, {TELA: tela, "background": fundo}, rodando, bloqueada, perdido)


def minutos(previsao) -> tuple:
    return (previsao.maquina_id,
            None if previsao.inicio is None else (previsao.inicio - AGORA).total_seconds() / 60,
            None if previsao.fim is None else (previsao.fim - AGORA).total_seconds() / 60)


# -- Cenário 1: duas máquinas, cinco jobs, os mais longos primeiro ----------------------

def test_cenario_1_duas_maquinas_cinco_jobs_mais_longos_primeiro() -> None:
    jobs = [job("j10", 10 * 60), job("j50", 50 * 60), job("j30", 30 * 60), job("j20", 20 * 60), job("j40", 40 * 60)]
    previsoes = {p.job_id: p for p in prever(jobs, [maquina("A"), maquina("B")], AGORA)}

    assert [p.job_id for p in sorted(previsoes.values(), key=lambda p: p.posicao)] == ["j50", "j40", "j30", "j20", "j10"]
    assert minutos(previsoes["j50"]) == ("A", 0, 50)
    assert minutos(previsoes["j40"]) == ("B", 0, 40)
    assert minutos(previsoes["j30"]) == ("B", 40, 70)
    assert minutos(previsoes["j20"]) == ("A", 50, 70)
    assert minutos(previsoes["j10"]) == ("A", 70, 80)  # empate em 70: a máquina A pelo nome
    linhas = [f"  {p.posicao}. {p.job_id} -> máquina {m}: início +{i:.0f} min, término +{f:.0f} min"
              for p in sorted(previsoes.values(), key=lambda p: p.posicao) for m, i, f in [minutos(p)]]
    print("\ncenário 1:\n" + "\n".join(linhas))


def test_despacho_segue_a_mesma_ordem_da_previsao() -> None:
    jobs = [job("curto", 60), job("longo", 600)]
    assert proximo_job(maquina("A"), TELA, jobs).id == "longo"


# -- Ordem ----------------------------------------------------------------------------

def test_prioridade_maior_vem_antes_de_tudo() -> None:
    jobs = [job("longo", 9999, chegada=0), job("urgente", 10, prioridade=5, chegada=50)]
    assert [j.id for j in ordenar(jobs)] == ["urgente", "longo"]


def test_posicao_manual_vem_antes_de_quem_nao_tem() -> None:
    jobs = [job("a", 900), job("b", 10, posicao=2), job("c", 10, posicao=1)]
    assert [j.id for j in ordenar(jobs)] == ["c", "b", "a"]


def test_lotes_seguem_a_ordem_de_chegada_e_o_mais_longo_so_dentro_do_lote() -> None:
    jobs = [job("l1-curto", 10, lote="L1", chegada=0), job("l2-longo", 999, lote="L2", chegada=5),
            job("l1-longo", 500, lote="L1", chegada=0)]
    assert [j.id for j in ordenar(jobs)] == ["l1-longo", "l1-curto", "l2-longo"]


def test_job_sem_estimativa_vai_depois_dos_que_tem_no_lote() -> None:
    jobs = [job("sem", None), job("pequeno", 1)]
    assert [j.id for j in ordenar(jobs)] == ["pequeno", "sem"]


def test_desempate_final_pelo_id_e_estavel() -> None:
    assert [j.id for j in ordenar([job("b"), job("a")])] == ["a", "b"]


# -- Cenário 5 e regra de tela -----------------------------------------------------------

def test_cenario_5_um_job_de_tela_por_maquina() -> None:
    a = maquina("A", tela=3)  # mesmo que a máquina diga 3, tela é uma por vez
    assert vagas_livres(a, TELA) == 1
    ocupada = maquina("A", tela=3, rodando=(EmExecucao("x", TELA, 100),))
    assert vagas_livres(ocupada, TELA) == 0
    assert proximo_job(ocupada, TELA, [job("j1", maquinas=frozenset({"A"}))]) is None
    previsoes = prever([job("j1", 60, maquinas=frozenset({"A"})), job("j2", 60, maquinas=frozenset({"A"}))], [a], AGORA)
    assert [minutos(p) for p in previsoes] == [("A", 0, 1), ("A", 1, 2)]


def test_segundo_plano_usa_a_capacidade_do_pool() -> None:
    m = maquina("A", tela=0, fundo=2)
    assert vagas_livres(m, "background") == 2
    previsoes = prever([job(f"j{i}", 60, pool="background", maquinas=frozenset({"A"})) for i in range(3)], [m], AGORA)
    assert [minutos(p) for p in previsoes] == [("A", 0, 1), ("A", 0, 1), ("A", 1, 2)]


# -- Máquinas e motivos ---------------------------------------------------------------------

def test_job_vai_so_para_maquina_compativel() -> None:
    previsao = prever([job("j", 60, maquinas=frozenset({"B"}))], [maquina("A"), maquina("B")], AGORA)[0]
    assert previsao.maquina_id == "B"
    assert proximo_job(maquina("A"), TELA, [job("j", maquinas=frozenset({"B"}))]) is None


def test_sem_maquina_compativel_diz_o_motivo() -> None:
    previsao = prever([job("j", 60, maquinas=frozenset())], [maquina("A")], AGORA)[0]
    assert (previsao.maquina_id, previsao.inicio, previsao.motivos) == (None, None, (SEM_MAQUINA_COMPATIVEL,))


@pytest.mark.parametrize("m,motivo", [
    (maquina("A", online=False), MAQUINA_SEM_SINAL),
    (maquina("A", bloqueada=True), SESSAO_BLOQUEADA),
    (maquina("A", perdido=True), JOB_PERDIDO_NA_MAQUINA),
])
def test_maquina_indisponivel_nao_recebe_e_diz_por_que(m: Maquina, motivo: str) -> None:
    previsao = prever([job("j", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0]
    assert previsao.inicio is None and previsao.motivos == (motivo,)
    assert proximo_job(m, TELA, [job("j", maquinas=frozenset({"A"}))]) is None
    assert disponivel(m) is False


def test_job_rodando_sem_previsao_deixa_os_seguintes_sem_inicio_com_motivo() -> None:
    m = maquina("A", rodando=(EmExecucao("rodando", TELA, None, ACIMA_DA_ESTIMATIVA),))
    previsao = prever([job("j", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0]
    assert (previsao.maquina_id, previsao.inicio, previsao.fim) == ("A", None, None)
    assert previsao.motivos == (ACIMA_DA_ESTIMATIVA,) and previsao.aguardando == "rodando"


def test_rodando_sem_motivo_informado_usa_aguardando_sem_previsao() -> None:
    m = maquina("A", rodando=(EmExecucao("rodando", TELA, None),))
    assert prever([job("j", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0].motivos == (AGUARDANDO_SEM_PREVISAO,)


def test_job_sem_estimativa_deixa_os_seguintes_da_maquina_sem_previsao() -> None:
    jobs = [job("novo", None, motivos=(SEM_HISTORICO,), maquinas=frozenset({"A"}), chegada=0),
            job("depois", 60, maquinas=frozenset({"A"}), lote="L2", chegada=1)]
    novo, depois = prever(jobs, [maquina("A")], AGORA)
    assert minutos(novo) == ("A", 0, None) and novo.motivos == (SEM_HISTORICO,) and novo.aguardando is None
    assert minutos(depois) == ("A", None, None) and depois.motivos == (AGUARDANDO_SEM_PREVISAO,)
    assert depois.aguardando == "novo"  # o motivo nomeia quem segura a fila


def test_quem_segura_a_fila_continua_o_mesmo_ate_alguem_ter_previsao() -> None:
    m = maquina("A", rodando=(EmExecucao("rodando", TELA, None),))
    jobs = [job("j1", 60, maquinas=frozenset({"A"}), chegada=0), job("j2", 60, maquinas=frozenset({"A"}), lote="L2", chegada=1)]
    j1, j2 = prever(jobs, [m], AGORA)
    assert (j1.aguardando, j2.aguardando) == ("rodando", "rodando")
    livre = prever(jobs, [maquina("A")], AGORA)
    assert [p.aguardando for p in livre] == [None, None]


def test_prefere_maquina_com_previsao_a_maquina_sem() -> None:
    a = maquina("A", rodando=(EmExecucao("x", TELA, None),))
    b = maquina("B", rodando=(EmExecucao("y", TELA, 300),))
    assert minutos(prever([job("j", 60)], [a, b], AGORA)[0]) == ("B", 5, 6)


def test_restante_negativo_conta_como_livre_agora() -> None:
    m = maquina("A", rodando=(EmExecucao("x", TELA, -30),))
    assert minutos(prever([job("j", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0]) == ("A", 0, 1)


def test_capacidade_zero_ou_negativa_nao_cria_vaga() -> None:
    m = Maquina("A", True, {TELA: -1})
    assert prever([job("j", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0].maquina_id is None


# -- Retomada e repetição --------------------------------------------------------------------

def test_retomada_volta_para_a_mesma_maquina() -> None:
    jobs = [job("retomada", 60, obrigatoria="B")]
    assert prever(jobs, [maquina("A"), maquina("B")], AGORA)[0].maquina_id == "B"
    assert proximo_job(maquina("A"), TELA, jobs) is None
    assert proximo_job(maquina("B"), TELA, jobs).id == "retomada"
    assert maquina_da_retomada("B", estado_central=False) == "B"
    assert maquina_da_retomada("B", estado_central=True) is None


def test_retomada_espera_a_maquina_dela_mesmo_sem_sinal() -> None:
    previsao = prever([job("r", 60, obrigatoria="B")], [maquina("A"), maquina("B", online=False)], AGORA)[0]
    assert previsao.maquina_id is None and previsao.motivos == (MAQUINA_SEM_SINAL,)


def test_tela_nunca_repete_sozinha_salvo_declarado() -> None:
    assert pode_repetir_sozinho(TELA, False) is False
    assert pode_repetir_sozinho(TELA, True) is True
    assert pode_repetir_sozinho("background", False) is True


# -- Cenários 3 e 4 ------------------------------------------------------------------------

def test_cenario_3_grupo_nunca_se_divide() -> None:
    itens = [{"chave": "5081", "grupo": "5081"}, {"chave": "5066"}, {"chave": "5076", "grupo": "5081"},
             {"chave": "5075", "grupo": "5081"}, {"chave": "5100", "grupo": "5099"}]
    grupos = agrupar(itens)
    assert [[i["chave"] for i in g] for g in grupos] == [["5081", "5076", "5075"], ["5066"], ["5100"]]
    print(f"\ncenário 3: {len(itens)} itens -> {len(grupos)} jobs; matriz 5081 e filiais no mesmo job")


def test_lider_do_grupo_vai_primeiro_mesmo_chegando_depois() -> None:
    itens = [{"chave": "5076", "grupo": "5081"}, {"chave": 5081, "grupo": 5081}]
    assert [str(i["chave"]) for i in agrupar(itens)[0]] == ["5081", "5076"]


def test_cenario_4_mesmo_pedido_tem_a_mesma_chave() -> None:
    a = chave_de_duplicata(1, ["5081", "5066"], {"competencia": "10/2026"})
    b = chave_de_duplicata(1, ["5066", "5081", "5066"], {"competencia": "10/2026"})
    assert a == b and len(a) == 64
    assert a != chave_de_duplicata(1, ["5081"], {"competencia": "10/2026"})
    assert a != chave_de_duplicata(2, ["5081", "5066"], {"competencia": "10/2026"})
    assert a != chave_de_duplicata(1, ["5081", "5066"], {"competencia": "11/2026"})


def test_regras_sao_imutaveis() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        job("x").prioridade = 9  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        maquina("A").online = False  # type: ignore[misc]


# -- Casos de borda apontados pelo teste de mutação --------------------------------------
# Textos montados em tempo de execução: no Portal os pools e ids vêm do banco, e um "is"
# no lugar de "==" passaria nos testes com literais.

def _t(*partes: str) -> str:
    return "".join(partes)


TELA_DO_BANCO = _t("inter", "active")


def test_borda_tela_vinda_do_banco_tambem_e_uma_por_maquina() -> None:
    m = Maquina("A", True, {TELA_DO_BANCO: 3})
    assert vagas_livres(m, TELA_DO_BANCO) == 1
    previsoes = prever([job(f"j{i}", 60, pool=TELA_DO_BANCO, maquinas=frozenset({"A"})) for i in range(2)], [m], AGORA)
    assert [minutos(p) for p in previsoes] == [("A", 0, 1), ("A", 1, 2)]


def test_borda_jobs_de_outro_pool_nao_ocupam_a_vaga() -> None:
    m = Maquina("A", True, {TELA: 1, "background": 2, "browser": 1},
                (EmExecucao("t", TELA, 60), EmExecucao("b", _t("back", "ground"), 60)))
    assert vagas_livres(m, "background") == 1
    assert vagas_livres(m, "browser") == 1
    assert vagas_livres(m, TELA) == 0
    previsoes = prever([job("n", 30, pool="browser", maquinas=frozenset({"A"}))], [m], AGORA)
    assert minutos(previsoes[0]) == ("A", 0, 0.5)
    fundo = prever([job("f", 30, pool="background", maquinas=frozenset({"A"}))], [m], AGORA)
    assert minutos(fundo[0]) == ("A", 0, 0.5)


def test_borda_tela_com_fundo_rodando_continua_livre() -> None:
    m = Maquina("A", True, {TELA: 1, "background": 1}, (EmExecucao("b", "background", 600),))
    assert vagas_livres(m, TELA) == 1
    assert minutos(prever([job("t", 60, maquinas=frozenset({"A"}))], [m], AGORA)[0]) == ("A", 0, 1)


@pytest.mark.parametrize("capacidade,rodando,livres", [(2, 1, 1), (3, 2, 1), (1, 2, -1)])
def test_borda_vagas_livres_e_capacidade_menos_rodando(capacidade: int, rodando: int, livres: int) -> None:
    m = Maquina("A", True, {"background": capacidade}, tuple(EmExecucao(f"r{i}", "background", 60) for i in range(rodando)))
    assert vagas_livres(m, "background") == livres


def test_borda_pool_que_a_maquina_nao_tem_nao_tem_vaga() -> None:
    m = Maquina("A", True, {"background": 2})
    assert vagas_livres(m, "browser") == 0
    assert proximo_job(m, "browser", [job("j", pool="browser", maquinas=frozenset({"A"}))]) is None


def test_borda_capacidade_reduzida_com_jobs_rodando_nao_despacha() -> None:
    m = Maquina("A", True, {"background": 1}, (EmExecucao("r1", "background", 60), EmExecucao("r2", "background", 60)))
    assert proximo_job(m, "background", [job("j", pool="background", maquinas=frozenset({"A"}))]) is None


def test_borda_maquina_indisponivel_antes_de_uma_disponivel() -> None:
    previsao = prever([job("j", 60)], [maquina("A", online=False), maquina("B")], AGORA)[0]
    assert minutos(previsao) == ("B", 0, 1)


def test_borda_job_sem_maquina_nao_impede_os_seguintes() -> None:
    jobs = [job("orfao", 600, maquinas=frozenset({"Z"})), job("normal", 60)]
    previsoes = {p.job_id: p for p in prever(jobs, [maquina("A")], AGORA)}
    assert previsoes["orfao"].maquina_id is None
    assert minutos(previsoes["normal"]) == ("A", 0, 1)


@pytest.mark.parametrize("primeiro", [
    job("outro-pool", 999, pool="browser", maquinas=frozenset({"A"})),
    job("outro-pool-b", 999, pool="background", maquinas=frozenset({"A"})),
    job("outra-maquina", 999, obrigatoria="Z"),
    job("incompativel", 999, maquinas=frozenset({"Z"})),
])
def test_borda_despacho_pula_o_que_nao_serve_e_pega_o_seguinte(primeiro: JobNaFila) -> None:
    assert proximo_job(maquina("A"), TELA, [primeiro, job("serve", 10)]).id == "serve"


def test_borda_despacho_com_pool_vindo_do_banco() -> None:
    assert proximo_job(maquina("A"), TELA, [job("j", pool=TELA_DO_BANCO)]).id == "j"


def test_borda_obrigatoria_de_outra_maquina_com_nome_menor() -> None:
    assert proximo_job(maquina("B"), TELA, [job("r", obrigatoria="A")]) is None
    assert proximo_job(maquina(_t("A")), TELA, [job("r", obrigatoria=_t("", "A"))]).id == "r"


def test_borda_posicao_comeca_em_1() -> None:
    posicoes = {p.job_id: p.posicao for p in prever([job("a", 10), job("b", 20)], [maquina("A")], AGORA)}
    assert posicoes == {"b": 1, "a": 2}
    assert prever([job("unico", 10)], [maquina("A")], AGORA)[0].posicao == 1


def test_borda_prioridades_positivas_diferentes() -> None:
    # ids escolhidos para o desempate final apontar o contrário da prioridade
    assert [j.id for j in ordenar([job("a-dois", prioridade=2), job("b-cinco", prioridade=5)])] == ["b-cinco", "a-dois"]


def test_borda_estimativa_zero_vem_depois_de_meio_segundo() -> None:
    assert [j.id for j in ordenar([job("zero", 0.0), job("meio", 0.5)])] == ["meio", "zero"]


def test_borda_padroes_da_maquina_disponivel() -> None:
    assert disponivel(Maquina("A", True, {TELA: 1})) is True


def test_borda_tela_vinda_do_banco_nao_repete_sozinha() -> None:
    assert pode_repetir_sozinho(TELA_DO_BANCO, False) is False


def test_borda_duplicata_nao_depende_da_ordem_dos_parametros_e_e_estavel() -> None:
    a = chave_de_duplicata(1, ["5066"], {"competencia": "10/2026", "modo": "completo"})
    b = chave_de_duplicata(1, ["5066"], {"modo": "completo", "competencia": "10/2026"})
    assert a == b
    assert chave_de_duplicata(1, ["5066"], {"observação": "competência"}) == \
        "d7244d92a6d948209881773bbeb4015cdc35c783351c6d7d443e7a91f40b5364"  # valor fixo: a chave não muda entre versões


def test_borda_previsao_e_execucao_sao_imutaveis() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        EmExecucao("x", TELA, 1).restante_s = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        prever([job("a")], [maquina("A")], AGORA)[0].inicio = None  # type: ignore[misc]


def test_borda_vaga_de_fundo_nao_pega_job_de_tela_que_vem_antes() -> None:
    m = Maquina("A", True, {TELA: 1, "background": 1})
    jobs = [job("tela", 999, maquinas=frozenset({"A"})), job("fundo", 10, pool="background", maquinas=frozenset({"A"}))]
    assert proximo_job(m, "background", jobs).id == "fundo"


def test_borda_job_rodando_com_pool_vindo_do_banco_ocupa_a_vaga() -> None:
    m = Maquina("A", True, {"background": 1}, (EmExecucao("r", _t("back", "ground"), 60),))
    previsao = prever([job("f", 60, pool="background", maquinas=frozenset({"A"}))], [m], AGORA)[0]
    assert minutos(previsao) == ("A", 1, 2)
