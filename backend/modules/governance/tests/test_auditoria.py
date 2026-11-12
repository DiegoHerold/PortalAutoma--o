"""Auditoria: tipos de evento, filtros de data no fuso de São Paulo e o que o registro de requisições pega."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from modules.governance.api.registro_de_requisicoes import deve_registrar, recurso_da_rota
from modules.governance.domain.auditoria import FiltroInvalido, intervalo, tipo_do_evento, validar_agrupamento, validar_tipo


@pytest.mark.parametrize("acao,ator,tipo", [
    ("login_succeeded", "user", "acesso"), ("login_failed", "user", "acesso"), ("tela.aberta", "user", "acesso"),
    ("direto.sessao.aberta", "direct_instance", "acesso"), ("direto.desafio.recusado", "direct_instance", "acesso"),
    ("execucao.telas.vistas", "user", "execucao"), ("schedule.trigger", "user", "execucao"),
    ("automacao.arquivo.baixado", "user", "execucao"),
    ("maquina.cadastrada", "user", "alteracao"), ("api.post", "user", "alteracao"), ("team_created", "user", "alteracao"),
    ("retencao.aplicada", "system", "sistema"), ("direto.inscricao", "direct_instance", "sistema"),
])
def test_tipo_do_evento(acao, ator, tipo) -> None:
    assert tipo_do_evento(acao, ator) == tipo


def test_filtros_validos_e_invalidos() -> None:
    assert validar_tipo(None) is None and validar_tipo("") is None and validar_tipo("acesso") == "acesso"
    with pytest.raises(FiltroInvalido, match="tipo"):
        validar_tipo("tudo")
    assert validar_agrupamento("usuario") == "usuario"
    with pytest.raises(FiltroInvalido, match="por"):
        validar_agrupamento("mes")


def test_intervalo_no_fuso_de_sao_paulo() -> None:
    sp = ZoneInfo("America/Sao_Paulo")
    de, ate = intervalo(date(2026, 11, 10), date(2026, 11, 12))
    assert de == datetime(2026, 11, 10, tzinfo=sp) and ate == datetime(2026, 11, 13, tzinfo=sp)  # inclui o dia 12 inteiro
    assert intervalo(None, None) == (None, None)
    with pytest.raises(FiltroInvalido, match="depois"):
        intervalo(date(2026, 11, 12), date(2026, 11, 10))


@pytest.mark.parametrize("metodo,caminho,registra", [
    ("POST", "/api/v1/maquinas", True), ("PUT", "/api/v1/schedules/12", True), ("PATCH", "/api/v1/schedules/12", True),
    ("DELETE", "/api/v1/maquinas/mch_1", True),
    ("GET", "/api/v1/maquinas", False),  # leitura não entra
    ("POST", "/api/v1/auth/login", False),  # o login já é registrado
    ("POST", "/api/v1/direto/jobs/x/eventos", False), ("PUT", "/api/v1/direto/jobs/x/imagens/i", False),  # máquinas
    ("POST", "/api/v1/agents/register", False), ("POST", "/api/v1/governance/auditoria/tela", False),
    ("POST", "/outra/coisa", False),
])
def test_o_que_o_registro_de_requisicoes_pega(metodo, caminho, registra) -> None:
    assert deve_registrar(metodo, caminho, "/api/v1") is registra


def test_recurso_da_rota() -> None:
    assert recurso_da_rota("/api/v1/schedules/12/pause", "/api/v1") == ("schedules", "12")
    assert recurso_da_rota("/api/v1/maquinas", "/api/v1") == ("maquinas", "-")
    assert recurso_da_rota("/api/v1/", "/api/v1") == ("portal", "-")
