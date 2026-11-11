"""Estado de "Acompanhar uma execução" a partir dos eventos da automação."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modules.telemetry.domain.acompanhamento import EventoDaAutomacao, estado

T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def ev(n: int, tipo_evento: str, segundos: float, tentativa: str = "t1", /, **payload) -> EventoDaAutomacao:
    # Texto montado em tempo de execução, como o que vem do banco: "is" no lugar de "==" falharia.
    tipo = "".join(list(tipo_evento))
    return EventoDaAutomacao(f"e{n:03d}", tipo, payload, T0 + timedelta(seconds=segundos), "".join(list(tentativa)), n)


def test_sem_eventos_tudo_vazio() -> None:
    e = estado([], T0, rodando=True)
    assert (e["etapa_atual"], e["item_atual"], e["tela"], e["passos"], e["atencoes"]) == (None, None, None, [], [])


def test_etapa_e_item_em_andamento_sao_os_abertos_mais_recentes() -> None:
    eventos = [
        ev(1, "item.iniciado", 0, item="5066", rotulo="Empresa 5066"),
        ev(2, "etapa.iniciada", 1, etapa="trocar_empresa", item="5066"),
        ev(3, "etapa.concluida", 30, etapa="trocar_empresa", item="5066", situacao="ok"),
        ev(4, "etapa.iniciada", 31, etapa="rubricas", item="5066", tarefas_previstas=50),
    ]
    e = estado(eventos, T0 + timedelta(seconds=60), rodando=True)
    assert e["etapa_atual"] == {"etapa": "rubricas", "item": "5066", "desde": (T0 + timedelta(seconds=31)).isoformat(),
                                "tarefas_previstas": 50}
    assert e["item_atual"]["item"] == "5066" and e["item_atual"]["rotulo"] == "Empresa 5066"


def test_item_concluido_sai_do_andamento() -> None:
    eventos = [ev(1, "item.iniciado", 0, item="5066"), ev(2, "item.concluido", 5, item="5066", situacao="ok")]
    assert estado(eventos, T0, rodando=True)["item_atual"] is None


def test_tela_atual_e_o_ultimo_passo_com_imagem_e_conta_n_segundos() -> None:
    eventos = [
        ev(1, "passo", 0, rotulo="Abriu Domínio", tipo="abriu", imagem_id="img1"),
        ev(2, "passo", 10, rotulo="Clicou em Empresas", tipo="acao", imagem_id="img2"),
        ev(3, "passo", 12, rotulo="Sem imagem", tipo="acao"),
    ]
    e = estado(eventos, T0 + timedelta(seconds=55), rodando=True)
    assert e["tela"]["imagem_id"] == "img2" and e["tela"]["rotulo"] == "Clicou em Empresas"
    assert e["tela"]["segundos_nesta_tela"] == 45
    assert [p["imagem_id"] for p in e["passos"]] == ["img1", "img2", None]


def test_espera_atualizada_usa_o_desde_dela_sem_imagem_nova() -> None:
    eventos = [
        ev(1, "passo", 0, rotulo="Gerando relatório", tipo="acao", imagem_id="img1"),
        ev(2, "espera.atualizada", 40, desde=(T0 + timedelta(seconds=5)).isoformat(), rotulo="Aguardando o Domínio"),
    ]
    tela = estado(eventos, T0 + timedelta(seconds=65), rodando=True)["tela"]
    assert tela["segundos_nesta_tela"] == 60 and tela["espera_rotulo"] == "Aguardando o Domínio"


def test_espera_de_antes_do_ultimo_passo_nao_vale() -> None:
    eventos = [
        ev(1, "espera.atualizada", 0, desde=T0.isoformat()),
        ev(2, "passo", 30, rotulo="Nova tela", tipo="acao", imagem_id="img2"),
    ]
    assert estado(eventos, T0 + timedelta(seconds=40), rodando=True)["tela"]["segundos_nesta_tela"] == 10


def test_depois_do_fim_nao_conta_tempo_na_tela() -> None:
    eventos = [ev(1, "passo", 0, rotulo="x", tipo="acao", imagem_id="img1"),
               ev(2, "execucao.concluida", 5, situacao="ok", resumo="3 empresas")]
    e = estado(eventos, T0 + timedelta(hours=1), rodando=False)
    assert e["tela"]["segundos_nesta_tela"] is None
    assert e["conclusao"]["situacao"] == "ok" and e["conclusao"]["resumo"] == "3 empresas"


def test_o_agora_vem_so_da_tentativa_mais_recente() -> None:
    """Retomada: a etapa aberta da tentativa que caiu não é a etapa de agora."""
    eventos = [
        ev(1, "etapa.iniciada", 0, "t1", etapa="rubricas", item="5066"),
        ev(2, "etapa.iniciada", 100, "t2", etapa="txt", item="5066"),
    ]
    assert estado(eventos, T0 + timedelta(seconds=120), rodando=True)["etapa_atual"]["etapa"] == "txt"


def test_pausa_em_curso_e_atencoes() -> None:
    eventos = [
        ev(1, "pausa.iniciada", 0, motivo="espera_externa", detalhe="Fila do Domínio"),
        ev(2, "atencao", 3, item="5081", motivo="Rubrica sem conta contábil"),
    ]
    e = estado(eventos, T0, rodando=True)
    assert e["pausa"]["motivo"] == "espera_externa" and e["pausa"]["detalhe"] == "Fila do Domínio"
    assert [a["item"] for a in e["atencoes"]] == ["5081"]
    eventos.append(ev(3, "pausa.concluida", 9, motivo="espera_externa"))
    assert estado(eventos, T0, rodando=True)["pausa"] is None


def test_limite_de_passos_guarda_os_mais_recentes() -> None:
    eventos = [ev(i, "passo", i, rotulo=f"p{i}", tipo="acao") for i in range(100)]
    passos = estado(eventos, T0, rodando=True, limite_passos=10)["passos"]
    assert [p["rotulo"] for p in passos] == [f"p{i}" for i in range(90, 100)]


def test_cenario_misturado_escolhe_o_aberto_mais_recente_de_cada_tipo() -> None:
    """Todos os tipos juntos, com mais de uma etapa, item e pausa abertos e eventos depois do progresso."""
    eventos = [
        ev(1, "execucao.iniciada", 0),
        ev(2, "item.iniciado", 1, item="5081", rotulo="Matriz 5081"),
        ev(3, "etapa.iniciada", 2, etapa="trocar_empresa", item="5081", tarefas_previstas=1),
        ev(4, "pausa.iniciada", 3, motivo="reinicio", detalhe="Domínio reabrindo"),
        ev(5, "progresso", 4, atual=1, total=3, rotulo="empresa 1 de 3"),
        ev(6, "atencao", 5, item="5081", motivo="Rubrica sem conta"),
        ev(7, "item.iniciado", 6, item="5076", rotulo="Filial 5076"),
        ev(8, "etapa.iniciada", 7, etapa="rubricas", item="5076", tarefas_previstas=40),
        ev(9, "pausa.iniciada", 8, motivo="espera_externa", detalhe="Fila do Domínio"),
        ev(10, "progresso", 9, atual=2, total=3, rotulo="empresa 2 de 3"),
        ev(11, "passo", 10, rotulo="Abriu Rubricas", tipo="abriu", imagem_id="img1"),
        ev(12, "log", 11, nivel="info", texto="x"),
        ev(13, "atencao", 12, item="5076", motivo="Centro sem rubrica"),
        ev(14, "espera.atualizada", 13, desde=(T0 + timedelta(seconds=10)).isoformat(), rotulo="Aguardando"),
        ev(15, "etapa.iniciada", 14, etapa="txt", item="5075"),
        ev(16, "etapa.concluida", 15, etapa="txt", item="5075", situacao="ok"),
        ev(17, "execucao.concluida", 16, situacao="atencao", resumo="2 de 3"),
        ev(18, "fim", 17),
    ]
    e = estado(eventos, T0 + timedelta(seconds=40), rodando=True)
    assert e["item_atual"] == {"item": "5076", "rotulo": "Filial 5076", "desde": (T0 + timedelta(seconds=6)).isoformat()}
    assert e["etapa_atual"] == {"etapa": "rubricas", "item": "5076", "desde": (T0 + timedelta(seconds=7)).isoformat(),
                                "tarefas_previstas": 40}
    assert e["pausa"] == {"motivo": "espera_externa", "detalhe": "Fila do Domínio", "desde": (T0 + timedelta(seconds=8)).isoformat()}
    assert e["progresso"] == {"atual": 2, "total": 3, "rotulo": "empresa 2 de 3", "item": None}
    assert e["conclusao"]["situacao"] == "atencao"
    assert [a["motivo"] for a in e["atencoes"]] == ["Rubrica sem conta", "Centro sem rubrica"]
    assert [p["rotulo"] for p in e["passos"]] == ["Abriu Rubricas"]
    assert e["tela"]["segundos_nesta_tela"] == 30 and e["tela"]["espera_rotulo"] == "Aguardando"


def test_tentativa_atual_e_a_do_ultimo_evento_mesmo_com_nome_menor() -> None:
    """A tentativa "a" é a mais recente e "b" a antiga: comparar nomes daria a errada."""
    eventos = [
        ev(1, "etapa.iniciada", 0, "b", etapa="velha", item="1"),
        ev(2, "progresso", 1, "b", atual=9, total=9),
        ev(3, "etapa.iniciada", 50, "a", etapa="nova", item="1"),
        ev(4, "log", 51, "a", nivel="info", texto="x"),
    ]
    e = estado(eventos, T0 + timedelta(seconds=60), rodando=True)
    assert e["etapa_atual"]["etapa"] == "nova" and e["progresso"] is None
    invertidos = [ev(1, "etapa.iniciada", 0, "a", etapa="velha"), ev(2, "etapa.iniciada", 50, "c", etapa="nova"),
                  ev(3, "log", 51, "c", nivel="info", texto="x")]
    assert estado(invertidos, T0, rodando=True)["etapa_atual"]["etapa"] == "nova"


def test_espera_no_mesmo_instante_do_passo_vale_e_desde_invalido_cai_no_passo() -> None:
    no_mesmo = [ev(1, "passo", 10, rotulo="x", tipo="acao", imagem_id="i"),
                ev(2, "espera.atualizada", 10, desde=(T0 + timedelta(seconds=4)).isoformat(), rotulo="mesmo instante")]
    assert estado(no_mesmo, T0 + timedelta(seconds=10), rodando=True)["tela"]["segundos_nesta_tela"] == 6
    invalido = [ev(1, "passo", 10, rotulo="x", tipo="acao", imagem_id="i"),
                ev(2, "espera.atualizada", 12, desde="ontem à tarde")]
    assert estado(invalido, T0 + timedelta(seconds=15), rodando=True)["tela"]["segundos_nesta_tela"] == 5
    outro_evento = [ev(1, "passo", 10, rotulo="x", tipo="acao", imagem_id="i"), ev(2, "log", 12, nivel="info", texto="y")]
    assert estado(outro_evento, T0 + timedelta(seconds=15), rodando=True)["tela"]["espera_rotulo"] is None


def test_relogio_da_tela_nunca_fica_negativo_e_comeca_em_zero() -> None:
    passo = [ev(1, "passo", 10, rotulo="x", tipo="acao", imagem_id="i")]
    assert estado(passo, T0 + timedelta(seconds=10), rodando=True)["tela"]["segundos_nesta_tela"] == 0
    assert estado(passo, T0, rodando=True)["tela"]["segundos_nesta_tela"] == 0


def test_limite_padrao_de_passos_e_60() -> None:
    eventos = [ev(i, "passo", i, rotulo=f"p{i}", tipo="acao") for i in range(100)]
    assert len(estado(eventos, T0, rodando=True)["passos"]) == 60


def test_evento_e_imutavel() -> None:
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        ev(1, "passo", 0).tipo = "log"  # type: ignore[misc]


def test_outros_eventos_do_mesmo_item_nao_fecham_o_item_nem_viram_conclusao() -> None:
    eventos = [
        ev(1, "item.iniciado", 0, item="5076"),
        ev(2, "passo", 1, rotulo="x", tipo="acao", imagem_id="i", item="5076"),
        ev(3, "log", 2, nivel="info", texto="y", item="5076"),
        ev(4, "progresso", 3, atual=1, total=2, item="5076"),
    ]
    e = estado(eventos, T0, rodando=True)
    assert e["item_atual"]["item"] == "5076"
    sem_fim = [ev(1, "atencao", 0, item="5076", motivo="m"), ev(2, "etapa.iniciada", 1, etapa="a")]
    assert estado(sem_fim, T0, rodando=True)["conclusao"] is None


def test_atencao_depois_da_espera_nao_e_tomada_como_espera() -> None:
    eventos = [
        ev(1, "passo", 10, rotulo="x", tipo="acao", imagem_id="i"),
        ev(2, "espera.atualizada", 11, desde=(T0 + timedelta(seconds=5)).isoformat(), rotulo="Aguardando"),
        ev(3, "atencao", 12, item="1", motivo="m"),
    ]
    tela = estado(eventos, T0 + timedelta(seconds=20), rodando=True)["tela"]
    assert tela["segundos_nesta_tela"] == 15 and tela["espera_rotulo"] == "Aguardando"


def test_tentativa_antiga_com_nome_menor_fica_fora_do_agora() -> None:
    eventos = [
        ev(1, "progresso", 0, "a", atual=9, total=9),
        ev(2, "pausa.iniciada", 1, "a", motivo="reinicio"),
        ev(3, "etapa.iniciada", 50, "b", etapa="nova"),
    ]
    e = estado(eventos, T0, rodando=True)
    assert e["progresso"] is None and e["pausa"] is None and e["etapa_atual"]["etapa"] == "nova"
