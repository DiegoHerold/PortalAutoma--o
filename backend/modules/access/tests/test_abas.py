"""Abas dos papéis: ordem, validação, permissões que a aba dá e que ela tira."""

from __future__ import annotations

import pytest

from modules.access.domain.abas import (
    CHAVES,
    PapelInvalido,
    abas_efetivas,
    permissoes_com_abas,
    permissoes_para_ligar,
    slug_do_nome,
    validar_abas,
)


def test_validar_poe_na_ordem_do_menu_e_recusa_desconhecida() -> None:
    assert validar_abas(["/audit", "/fila", "/fila"]) == ["/fila", "/audit"]
    with pytest.raises(PapelInvalido, match="desconhecida"):
        validar_abas(["/fila", "/painel-secreto"])


def test_nulo_e_todas() -> None:
    assert abas_efetivas(None) == list(CHAVES)
    assert abas_efetivas(["/users", "/fila"]) == ["/fila", "/users"]


def test_aba_desligada_tira_so_as_permissoes_exclusivas_dela() -> None:
    gravadas = ["audit.read", "execution.read", "schedule.read", "schedule.trigger", "secret.manage"]
    assert permissoes_com_abas(gravadas, None) == gravadas  # papel de antes: nada muda
    sem_auditoria = permissoes_com_abas(gravadas, ["/fila", "/schedules", "/secrets"])
    assert sem_auditoria == ["execution.read", "schedule.read", "schedule.trigger", "secret.manage"]
    # execution.read é de várias abas: desligar a Fila não tira (o bloqueio é na tela)
    assert "execution.read" in permissoes_com_abas(gravadas, [])
    assert permissoes_com_abas(gravadas, []) == ["execution.read"]


def test_ligar_da_a_leitura_e_slug() -> None:
    assert permissoes_para_ligar(["/fila", "/historico", "/audit", "/categories"]) == ["audit.read", "execution.read"]
    assert slug_do_nome("  Analista Fiscal (Folha) ") == "analista-fiscal-folha"
    assert slug_do_nome("Gestão") == "gestao"
    with pytest.raises(PapelInvalido):
        slug_do_nome("!!!")
