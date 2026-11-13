"""Catálogo de configurações (limites e limpeza) e os casos de uso, sem banco."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from modules.governance.application.configuracoes import (
    AplicarLimpezaDoSistema,
    DefinirPrazoDeLimpeza,
    ListarLimpezas,
    PrazoGravado,
    dias_em_vigor,
)
from modules.governance.domain.configuracoes import (
    LIMITES,
    LIMPEZAS,
    ConfiguracaoInvalida,
    validar_limite,
    validar_prazo,
)


def test_catalogo_consistente() -> None:
    from modules.governance.infrastructure.adapters.limpeza import LIMPADORES

    chaves = [i.chave for i in LIMITES] + [i.chave for i in LIMPEZAS]
    assert len(chaves) == len(set(chaves)), "chave repetida no catálogo"
    for item in LIMITES:
        assert item.minimo <= item.padrao <= item.maximo, item.chave
        assert item.origem in {"portal", "arquivo"} and (item.origem == "portal" or item.variavel_de_ambiente)
    for item in LIMPEZAS:
        if item.editavel:
            assert item.chave in LIMPADORES, f"regra sem quem apague: {item.chave}"
            assert item.padrao_dias is None or item.minimo_dias <= item.padrao_dias <= item.maximo_dias, item.chave
        else:
            assert item.padrao_dias is None and item.chave not in LIMPADORES
    assert set(LIMPADORES) == {i.chave for i in LIMPEZAS if i.editavel}


def test_notificacoes_ficam_uma_semana_e_nunca_menos_de_dois_dias() -> None:
    assert dias_em_vigor("notificacoes", None) == 7
    with pytest.raises(ConfiguracaoInvalida):
        validar_prazo("notificacoes", 1)  # o detector olha 24 h: menos que isso repetiria avisos
    assert validar_prazo("notificacoes", None) is None  # desligar é permitido


def test_validacao_de_limites() -> None:
    assert validar_limite("execution.max_concurrent", 5) == 5
    with pytest.raises(ConfiguracaoInvalida):
        validar_limite("execution.max_concurrent", 0)
    with pytest.raises(ConfiguracaoInvalida, match=".env"):
        validar_limite("gateway.max_message_bytes", 2048)
    with pytest.raises(ConfiguracaoInvalida, match="desconhecido"):
        validar_limite("nao.existe", 1)
    with pytest.raises(ConfiguracaoInvalida, match="guardado sempre"):
        validar_prazo("sempre.auditoria", 30)


class _Repo:
    def __init__(self, prazos: dict[str, PrazoGravado] | None = None) -> None:
        self._prazos = dict(prazos or {})
        self.passadas: dict[str, int] = {}

    def prazos(self) -> dict[str, PrazoGravado]:
        return self._prazos

    def gravar_prazo(self, chave, dias, personalizado, por, agora) -> None:
        self._prazos[chave] = PrazoGravado(personalizado, dias, por, agora)

    def registrar_passada(self, chave, apagados, agora) -> None:
        self.passadas[chave] = apagados


class _Lista(list):
    def append(self, item) -> None:  # imita o repositório de auditoria
        super().append(item)


class _Transacao:
    def __init__(self) -> None:
        self.commits = self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_aplicar_limpeza_usa_o_padrao_respeita_o_desligado_e_isola_falha() -> None:
    agora = datetime(2026, 11, 13, 12, tzinfo=UTC)
    chamadas: dict[str, datetime] = {}

    def limpador(chave, apagados=3):
        def f(corte, lote):
            chamadas[chave] = corte
            return apagados
        return f

    def quebra(corte, lote):
        raise RuntimeError("tabela fora")

    repo = _Repo({"maquinas.recursos": PrazoGravado(True, None)})  # desligada por alguém
    auditoria, transacao = _Lista(), _Transacao()
    feito = AplicarLimpezaDoSistema(repo, {"notificacoes": limpador("notificacoes"),
                                           "maquinas.recursos": limpador("maquinas.recursos"),
                                           "interno.mensagens": quebra,
                                           "execucoes.decisoes": limpador("execucoes.decisoes", 0)},
                                    auditoria, transacao, agora=lambda: agora).execute()

    assert chamadas["notificacoes"] == agora - timedelta(days=7)
    assert "maquinas.recursos" not in chamadas  # sem prazo: nada sai
    assert feito == {"notificacoes": 3, "execucoes.decisoes": 0}
    assert transacao.rollbacks == 1  # a regra quebrada não levou as outras
    assert [e.resource_id for e in auditoria] == ["notificacoes"]  # só o que apagou algo vai à auditoria
    assert repo.passadas == {"notificacoes": 3, "execucoes.decisoes": 0}


def test_definir_prazo_e_voltar_ao_padrao() -> None:
    repo, auditoria, transacao = _Repo(), _Lista(), _Transacao()
    caso = DefinirPrazoDeLimpeza(repo, auditoria, transacao)
    caso.execute(None, "notificacoes", 14)
    assert ListarLimpezas(repo).execute()[0]["dias"] == 14
    caso.execute(None, "notificacoes", None, voltar_ao_padrao=True)
    linha = next(i for i in ListarLimpezas(repo).execute() if i["chave"] == "notificacoes")
    assert linha["dias"] == 7 and linha["personalizado"] is False
    assert [e.after["dias"] for e in auditoria] == [14, 7]
