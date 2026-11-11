"""Notificações: o que vira aviso, quem recebe, um por endereço e nada repetido."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from modules.telemetry.domain import notificacoes as n
from modules.telemetry.domain.notificacoes import (
    ATENCAO,
    ERRO,
    FILA_PARADA,
    MAQUINA_OFFLINE,
    TERMINO,
    Pessoa,
    PreferenciaInvalida,
    atencao,
    destinatarios,
    fila_parada,
    fim_de_execucao,
    maquina_offline,
    recente,
    validar_preferencia,
)

AGORA = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


def p(uid: int, email: str | None, *tipos: str, gestor: bool = False, minutos: int = 30) -> Pessoa:
    return Pessoa(uid, email, gestor, frozenset(tipos), minutos)


def todos(_pessoa: Pessoa, _automacao: int) -> bool:
    return True


# --- fim de execução -------------------------------------------------------------------------

@pytest.mark.parametrize("situacao", ["failed", "timed_out", "partially_succeeded"])
def test_execucao_com_erro_e_erro_e_termino_numa_ocorrencia_so(situacao: str) -> None:
    o = fim_de_execucao("exe_1", situacao, 7, "Folha", AGORA, "o Total não bateu")
    assert o.tipos == {ERRO, TERMINO} and o.chave == "fim:exe_1"
    assert (o.automation_id, o.execution_id, o.link, o.quando) == (7, "exe_1", "/execucoes/exe_1", AGORA)
    assert "o Total não bateu" in o.texto and o.titulo.startswith("Folha: terminou com erro")


def test_parcial_diz_que_parte_dos_itens_falhou() -> None:
    o = fim_de_execucao("exe_1", "partially_succeeded", 7, "Folha", AGORA)
    assert o.titulo == "Folha: terminou com erro em parte dos itens"
    assert o.texto == "A execução exe_1 terminou, mas parte dos itens falhou."


@pytest.mark.parametrize("situacao,titulo,texto", [
    ("succeeded", "Folha: concluída", "A execução exe_1 terminou."),
    ("cancelled", "Folha: cancelada", "A execução exe_1 foi cancelada."),
])
def test_execucao_sem_erro_e_so_termino(situacao: str, titulo: str, texto: str) -> None:
    o = fim_de_execucao("exe_1", situacao, 7, "Folha", AGORA, "não aparece")
    assert (o.tipos, o.titulo, o.texto) == ({TERMINO}, titulo, texto)


def test_falha_sem_motivo_e_automacao_sem_nome() -> None:
    o = fim_de_execucao("exe_1", "failed", None, None, AGORA)
    assert (o.titulo, o.texto) == ("Automação: terminou com erro", "A execução exe_1 terminou com erro.")


# --- atenção ---------------------------------------------------------------------------------

def test_atencao_uma_por_execucao_e_item() -> None:
    o = atencao("exe_1", "5081", "Rubrica 0450 sem conta", 7, "Folha", AGORA)
    assert (o.chave, o.tipos, o.titulo) == ("atencao:exe_1:5081", {ATENCAO}, "Folha: precisa de uma pessoa")
    assert o.texto == "O item 5081 precisa de uma pessoa: Rubrica 0450 sem conta"
    assert (o.automation_id, o.execution_id, o.link) == (7, "exe_1", "/execucoes/exe_1")
    sem = atencao("exe_1", None, None, None, None, AGORA)
    assert (sem.chave, sem.texto, sem.titulo) == ("atencao:exe_1:-", "A execução precisa de uma pessoa.",
                                                  "Automação: precisa de uma pessoa")


# --- máquina offline -------------------------------------------------------------------------

def test_maquina_offline_uma_por_queda() -> None:
    sinal = AGORA - timedelta(minutes=5)
    o = maquina_offline("mch_1", "FOLHA-01", sinal, False, AGORA)
    assert o is not None and o.chave == f"offline:mch_1:{sinal.isoformat()}" and o.tipos == {MAQUINA_OFFLINE}
    assert (o.titulo, o.link, o.automation_id, o.quando) == ("Máquina FOLHA-01 offline", "/maquinas", None, sinal)
    assert o.texto == "A máquina FOLHA-01 parou de dar sinal."
    outra = maquina_offline("mch_1", "FOLHA-01", sinal + timedelta(minutes=1), False, AGORA)
    assert outra is not None and outra.chave != o.chave  # nova queda, novo aviso


def test_maquina_online_sem_sinal_ou_caida_ha_mais_de_um_dia_nao_avisa() -> None:
    assert maquina_offline("m", "M", AGORA - timedelta(minutes=5), True, AGORA) is None
    assert maquina_offline("m", "M", None, False, AGORA) is None
    assert maquina_offline("m", "M", AGORA - timedelta(hours=24, seconds=1), False, AGORA) is None
    assert maquina_offline("m", "M", AGORA - timedelta(hours=24), False, AGORA) is not None


# --- fila parada -----------------------------------------------------------------------------

def test_fila_parada_conta_do_job_mais_antigo_ou_do_ultimo_inicio() -> None:
    antigo, novo = AGORA - timedelta(minutes=50), AGORA - timedelta(minutes=10)
    o = fila_parada([novo, antigo], None, AGORA, 30)
    assert o is not None and o.chave == f"fila_parada:{antigo.isoformat()}:30"
    assert (o.tipos, o.fila_minutos, o.link) == ({FILA_PARADA}, 30, "/fila")
    assert o.texto == "2 job(s) esperando e nenhum começou há mais de 30 min."
    # começou um job há 20 min: a parada conta dali
    assert fila_parada([antigo], AGORA - timedelta(minutes=20), AGORA, 30) is None
    depois = fila_parada([antigo], AGORA - timedelta(minutes=40), AGORA, 30)
    assert depois is not None and depois.chave == f"fila_parada:{(AGORA - timedelta(minutes=40)).isoformat()}:30"
    # início anterior ao job mais antigo não conta
    assert fila_parada([antigo], AGORA - timedelta(hours=3), AGORA, 30).chave == o.chave  # type: ignore[union-attr]


def test_fila_vazia_ou_dentro_do_tempo_nao_avisa() -> None:
    assert fila_parada([], None, AGORA, 30) is None
    assert fila_parada([AGORA - timedelta(minutes=29, seconds=59)], None, AGORA, 30) is None
    assert fila_parada([AGORA - timedelta(minutes=30)], None, AGORA, 30) is not None
    assert fila_parada([AGORA - timedelta(hours=25)], None, AGORA, 30) is None  # parada velha: não despeja


def test_recente() -> None:
    assert recente(AGORA, AGORA) and recente(AGORA - n.JANELA_DE_DETECCAO, AGORA)
    assert not recente(AGORA - n.JANELA_DE_DETECCAO - timedelta(seconds=1), AGORA) and not recente(None, AGORA)


# --- quem recebe -----------------------------------------------------------------------------

def test_recebe_so_quem_escolheu_o_tipo() -> None:
    o = fim_de_execucao("exe_1", "succeeded", 7, "Folha", AGORA)
    pessoas = [p(1, "a@x.com", TERMINO), p(2, "b@x.com", ERRO), p(3, "c@x.com")]
    assert destinatarios(o, pessoas, todos) == [(1, "a@x.com")]
    erro = fim_de_execucao("exe_2", "failed", 7, "Folha", AGORA)
    assert destinatarios(erro, pessoas, todos) == [(1, "a@x.com"), (2, "b@x.com")]


def test_um_por_endereco_mesmo_com_duas_pessoas_ou_dois_tipos() -> None:
    erro = fim_de_execucao("exe_2", "failed", 7, "Folha", AGORA)
    pessoas = [p(1, " Folha@X.com ", ERRO, TERMINO), p(2, "folha@x.com", ERRO), p(3, "outra@x.com", TERMINO)]
    assert destinatarios(erro, pessoas, todos) == [(1, "folha@x.com"), (3, "outra@x.com")]


def test_sem_endereco_valido_nao_recebe() -> None:
    o = fim_de_execucao("exe_1", "succeeded", 7, "Folha", AGORA)
    assert destinatarios(o, [p(1, None, TERMINO), p(2, "  ", TERMINO), p(3, "semarroba", TERMINO)], todos) == []


def test_so_quem_pode_ver_a_automacao() -> None:
    o = fim_de_execucao("exe_1", "succeeded", 7, "Folha", AGORA)
    vistos: list[tuple[int, int]] = []

    def pode(pessoa: Pessoa, automacao: int) -> bool:
        vistos.append((pessoa.user_id, automacao))
        return pessoa.user_id == 2

    assert destinatarios(o, [p(1, "a@x.com", TERMINO), p(2, "b@x.com", TERMINO), p(3, "c@x.com", ERRO)], pode) == [(2, "b@x.com")]
    assert vistos == [(1, 7), (2, 7)]  # quem não quer o tipo nem é consultado


def test_ocorrencia_sem_automacao_nao_consulta_permissao() -> None:
    o = maquina_offline("m", "M", AGORA - timedelta(minutes=1), False, AGORA)
    assert o is not None
    nunca = lambda *_: pytest.fail("não deveria consultar")  # noqa: E731
    assert destinatarios(o, [p(1, "g@x.com", MAQUINA_OFFLINE, gestor=True)], nunca) == [(1, "g@x.com")]


def test_maquina_e_fila_so_para_gestores() -> None:
    o = maquina_offline("m", "M", AGORA - timedelta(minutes=1), False, AGORA)
    assert o is not None
    pessoas = [p(1, "op@x.com", MAQUINA_OFFLINE), p(2, "g@x.com", MAQUINA_OFFLINE, gestor=True)]
    assert destinatarios(o, pessoas, todos) == [(2, "g@x.com")]


def test_fila_parada_so_para_quem_escolheu_aquele_tempo() -> None:
    o = fila_parada([AGORA - timedelta(hours=1)], None, AGORA, 30)
    assert o is not None
    pessoas = [p(1, "a@x.com", FILA_PARADA, gestor=True, minutos=30), p(2, "b@x.com", FILA_PARADA, gestor=True, minutos=45),
               p(3, "c@x.com", FILA_PARADA, MAQUINA_OFFLINE, gestor=True, minutos=45)]
    assert destinatarios(o, pessoas, todos) == [(1, "a@x.com")]


def test_minutos_de_fila_nao_atrapalham_os_outros_tipos() -> None:
    o = fim_de_execucao("exe_1", "succeeded", 7, "Folha", AGORA)
    assert destinatarios(o, [p(1, "a@x.com", TERMINO, FILA_PARADA, gestor=True, minutos=45)], todos) == [(1, "a@x.com")]


# --- preferência -----------------------------------------------------------------------------

def test_preferencia_valida() -> None:
    assert validar_preferencia(["erro", "termino"], 30, False) == (frozenset({"erro", "termino"}), 30)
    assert validar_preferencia(["fila_parada"], 5, True) == (frozenset({"fila_parada"}), 5)
    assert validar_preferencia([], 1440, True) == (frozenset(), 1440)


@pytest.mark.parametrize("tipos,minutos,gestor,trecho", [
    (["spam"], 30, True, "tipo desconhecido: spam"),
    (["maquina_offline"], 30, False, "só para administradores e gestores"),
    (["fila_parada", "erro"], 30, False, "só para administradores e gestores"),
    ([], 4, True, "de 5 a 1440 minutos"),
    ([], 1441, True, "de 5 a 1440 minutos"),
])
def test_preferencia_invalida(tipos: list[str], minutos: int, gestor: bool, trecho: str) -> None:
    with pytest.raises(PreferenciaInvalida, match=trecho):
        validar_preferencia(tipos, minutos, gestor)


def test_constantes() -> None:
    assert n.TIPOS == ("erro", "atencao", "maquina_offline", "fila_parada", "termino")
    assert n.SO_GESTORES == {"maquina_offline", "fila_parada"}
    assert (n.FILA_MINUTOS_PADRAO, n.FILA_MINUTOS_LIMITES, n.JANELA_DE_DETECCAO) == (30, (5, 1440), timedelta(hours=24))
    assert n.SITUACOES_DE_ERRO == {"failed", "timed_out", "partially_succeeded"}
    assert Pessoa(1, "a@x.com", False).tipos == frozenset() and Pessoa(1, "a@x.com", False).fila_minutos == 30


def test_ocorrencia_e_pessoa_sao_imutaveis() -> None:
    import dataclasses

    o = fim_de_execucao("exe_1", "succeeded", 7, "Folha", AGORA)
    with pytest.raises(dataclasses.FrozenInstanceError):
        o.titulo = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        p(1, "a@x.com").gestor = True  # type: ignore[misc]


def test_situacao_que_vem_de_fora_e_situacao_desconhecida() -> None:
    parcial = "".join(["partially_", "succeeded"])  # não é o mesmo objeto do literal
    cancelada = "".join(["cancel", "led"])
    assert fim_de_execucao("e", parcial, 7, "F", AGORA).titulo == "F: terminou com erro em parte dos itens"
    assert fim_de_execucao("e", cancelada, 7, "F", AGORA).titulo == "F: cancelada"
    assert fim_de_execucao("e", "aborted", 7, "F", AGORA).titulo == "F: concluída"  # antes de "cancelled" na ordem


def test_fila_parada_tempo_menor_tambem_nao_recebe_e_tempo_grande_vindo_de_fora() -> None:
    o = fila_parada([AGORA - timedelta(hours=1)], None, AGORA, 30)
    assert o is not None
    assert destinatarios(o, [p(1, "a@x.com", FILA_PARADA, gestor=True, minutos=15)], todos) == []
    grande = fila_parada([AGORA - timedelta(hours=20)], None, AGORA, 1000)
    assert grande is not None
    vindo_de_fora = int("1000")  # outro objeto, mesmo valor
    assert destinatarios(grande, [p(1, "a@x.com", FILA_PARADA, gestor=True, minutos=vindo_de_fora)], todos) == [(1, "a@x.com")]
