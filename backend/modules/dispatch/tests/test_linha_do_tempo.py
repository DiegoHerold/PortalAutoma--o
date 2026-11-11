"""Linha do tempo por máquina: recorte na janela, posição e fim nunca inventado."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from modules.dispatch.domain.linha_do_tempo import FEITO, PREVISTO, RODANDO, Bloco, marcas, montar

T0 = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
JANELA = (T0, T0 + timedelta(hours=10))
MAQ = [("A", "FOLHA-01"), ("B", "FOLHA-02")]


def h(horas: float) -> datetime:
    return T0 + timedelta(hours=horas)


def linha(resultado: list[dict], maquina: str) -> list[dict]:
    return next(m for m in resultado if m["maquina_id"] == maquina)["blocos"]


def test_posicao_em_porcentagem_da_janela() -> None:
    r = montar(MAQ, [Bloco("A", FEITO, h(1), h(3), situacao="succeeded")], *JANELA, agora=h(5))
    assert [(b["esquerda"], b["largura"], b["fim_conhecido"]) for b in linha(r, "A")] == [(10.0, 20.0, True)]
    assert linha(r, "B") == []


def test_recorta_o_que_passa_das_bordas_e_descarta_o_que_esta_fora() -> None:
    blocos = [Bloco("A", FEITO, h(-2), h(1)), Bloco("A", FEITO, h(9), h(12)), Bloco("A", FEITO, h(-5), h(-1)),
              Bloco("A", PREVISTO, h(11), h(12))]
    b = linha(montar(MAQ, blocos, *JANELA, agora=h(5)), "A")
    assert [(x["esquerda"], x["largura"], x["cortado_no_inicio"], x["cortado_no_fim"]) for x in b] == [
        (0.0, 10.0, True, False), (90.0, 10.0, False, True)]


def test_rodando_sem_previsao_vai_ate_agora_e_previsto_sem_termino_ate_o_fim_da_janela() -> None:
    blocos = [Bloco("A", RODANDO, h(4), None), Bloco("B", PREVISTO, h(6), None)]
    r = montar(MAQ, blocos, *JANELA, agora=h(5))
    rodando, previsto = linha(r, "A")[0], linha(r, "B")[0]
    assert (rodando["esquerda"], rodando["largura"], rodando["fim_conhecido"], rodando["fim"]) == (40.0, 10.0, False, None)
    assert (previsto["esquerda"], previsto["largura"], previsto["fim_conhecido"]) == (60.0, 40.0, False)


def test_rodando_com_previsao_usa_o_termino_previsto() -> None:
    r = montar(MAQ, [Bloco("A", RODANDO, h(4), h(7))], *JANELA, agora=h(5))
    assert (linha(r, "A")[0]["largura"], linha(r, "A")[0]["fim_conhecido"]) == (30.0, True)


def test_rodando_que_comecou_no_futuro_por_relogio_nao_fica_com_largura_negativa() -> None:
    r = montar(MAQ, [Bloco("A", RODANDO, h(5.5), None)], *JANELA, agora=h(5))
    assert linha(r, "A")[0]["largura"] == 0.6


def test_bloco_curto_tem_largura_minima_e_nunca_passa_de_100() -> None:
    blocos = [Bloco("A", FEITO, h(1), h(1) + timedelta(seconds=5)), Bloco("A", FEITO, h(9.999), h(10))]
    b = linha(montar(MAQ, blocos, *JANELA, agora=h(5)), "A")
    assert b[0]["largura"] == 0.6
    assert b[1]["esquerda"] + b[1]["largura"] <= 100.0


def test_ordem_por_inicio_e_maquina_desconhecida_ignorada() -> None:
    blocos = [Bloco("A", FEITO, h(3), h(4), automacao="b"), Bloco("A", FEITO, h(1), h(2), automacao="a"),
              Bloco("Z", FEITO, h(1), h(2))]
    r = montar(MAQ, blocos, *JANELA, agora=h(5))
    assert [b["automacao"] for b in linha(r, "A")] == ["a", "b"] and [m["maquina_id"] for m in r] == ["A", "B"]


def test_janela_invalida() -> None:
    with pytest.raises(ValueError):
        montar(MAQ, [], T0, T0, agora=T0)


def test_marcas_de_hora_cheia() -> None:
    m = marcas(T0 + timedelta(minutes=30), T0 + timedelta(hours=3, minutes=30))
    assert [x["quando"][11:16] for x in m] == ["09:00", "10:00", "11:00"]
    assert [round(x["posicao"], 2) for x in m] == [16.67, 50.0, 83.33]
    assert [x["quando"][11:16] for x in marcas(T0, T0 + timedelta(hours=2))] == ["08:00", "09:00", "10:00"]


def test_bordas_exatas_da_janela() -> None:
    blocos = [Bloco("A", FEITO, h(-1), h(0)),        # termina exatamente no início: fora
              Bloco("A", FEITO, h(10), h(11)),       # começa exatamente no fim: fora
              Bloco("A", FEITO, h(0), h(10))]        # ocupa a janela inteira, sem corte
    b = linha(montar(MAQ, blocos, *JANELA, agora=h(5)), "A")
    assert [(x["esquerda"], x["largura"], x["cortado_no_inicio"], x["cortado_no_fim"]) for x in b] == [(0.0, 100.0, False, False)]


def test_posicao_com_tres_casas() -> None:
    janela = (T0, T0 + timedelta(hours=3))
    b = linha(montar(MAQ, [Bloco("A", FEITO, h(1), h(2))], *janela, agora=h(2)), "A")[0]
    assert (b["esquerda"], b["largura"]) == (33.333, 33.333)
    assert [m["posicao"] for m in marcas(T0 + timedelta(minutes=20), T0 + timedelta(minutes=200))] == [22.222, 55.556, 88.889]


def test_tipo_vindo_de_fora_e_janela_ao_contrario() -> None:
    rodando = "".join(list(RODANDO))
    r = montar(MAQ, [Bloco("A", rodando, h(4), None)], *JANELA, agora=h(5))
    assert linha(r, "A")[0]["largura"] == 10.0
    with pytest.raises(ValueError):
        montar(MAQ, [], h(2), h(1), agora=T0)


def test_bloco_e_imutavel() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        Bloco("A", FEITO, h(1), h(2)).tipo = PREVISTO  # type: ignore[misc]
