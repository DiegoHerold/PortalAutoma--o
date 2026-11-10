"""Concessões por automação (decisão 6): regras puras."""

from __future__ import annotations

import pytest

from modules.access.domain.concessao import (
    ACOES,
    CONTROLAR,
    EDITAR_ITENS,
    EXECUTAR,
    VER_EXECUCOES,
    VER_TELAS_E_LOGS,
    AcaoInvalida,
    efetivas,
    normalizar_acoes,
    permitido,
)


def _nunca(_acao: str) -> bool:
    return False


def _sempre(_acao: str) -> bool:
    return True


def test_admin_pode_tudo_sem_concessao() -> None:
    assert all(permitido(a, admin=True, concedidas=(), legado_permite=_nunca) for a in ACOES)


def test_sem_concessao_e_sem_categoria_nao_pode_nada() -> None:
    assert not any(permitido(a, admin=False, concedidas=(), legado_permite=_nunca) for a in ACOES)


def test_telas_e_logs_so_por_concessao_mesmo_com_a_categoria_inteira() -> None:
    """Imagens e logs mostram dados de clientes: a permissão antiga da categoria não basta."""
    assert not permitido(VER_TELAS_E_LOGS, admin=False, concedidas=(), legado_permite=_sempre)
    assert not permitido(CONTROLAR, admin=False, concedidas=(), legado_permite=_sempre)
    assert not permitido(EDITAR_ITENS, admin=False, concedidas=(), legado_permite=_sempre)
    assert permitido(VER_TELAS_E_LOGS, admin=False, concedidas=(VER_TELAS_E_LOGS,), legado_permite=_nunca)


def test_ver_execucoes_e_executar_continuam_pela_categoria_antiga() -> None:
    pedidas: list[str] = []

    def legado(acao: str) -> bool:
        pedidas.append(acao)
        return acao == "can_view"

    assert permitido(VER_EXECUCOES, admin=False, concedidas=(), legado_permite=legado)
    assert not permitido(EXECUTAR, admin=False, concedidas=(), legado_permite=legado)
    assert pedidas == ["can_view", "can_execute"]


def test_concessao_implica_as_acoes_menores() -> None:
    assert efetivas([VER_TELAS_E_LOGS]) == {VER_TELAS_E_LOGS, VER_EXECUCOES}
    assert efetivas([CONTROLAR]) == {CONTROLAR, EXECUTAR, VER_EXECUCOES}
    assert efetivas([EXECUTAR]) == {EXECUTAR, VER_EXECUCOES}
    assert efetivas([EDITAR_ITENS]) == {EDITAR_ITENS, VER_EXECUCOES}
    assert efetivas([VER_EXECUCOES]) == {VER_EXECUCOES}
    # ver execuções não dá telas, executar não dá controle
    assert not permitido(VER_TELAS_E_LOGS, admin=False, concedidas=(VER_EXECUCOES, EXECUTAR), legado_permite=_nunca)
    assert not permitido(CONTROLAR, admin=False, concedidas=(EXECUTAR,), legado_permite=_nunca)


def test_normalizar_ordena_tira_repeticao_e_recusa_desconhecida() -> None:
    assert normalizar_acoes([EXECUTAR, VER_EXECUCOES, EXECUTAR]) == (VER_EXECUCOES, EXECUTAR)
    assert normalizar_acoes([]) == ()
    with pytest.raises(AcaoInvalida, match="apagar_tudo"):
        normalizar_acoes(["apagar_tudo", VER_EXECUCOES])


def test_acao_desconhecida_na_consulta_e_erro_e_nao_falso() -> None:
    with pytest.raises(AcaoInvalida):
        permitido("ver_tudo", admin=True, concedidas=(), legado_permite=_sempre)
