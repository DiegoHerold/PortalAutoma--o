"""Retenção por automação: prazo válido, corte e "sem prazo, nada sai"."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from modules.governance.application.retencao import AplicarRetencao, DefinirRetencao
from modules.governance.domain.retencao_por_automacao import (
    DIAS_MAXIMO,
    DIAS_MINIMO,
    PrazoInvalido,
    RetencaoDaAutomacao,
    corte,
    validar,
)

AGORA = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


def test_limites() -> None:
    assert (DIAS_MINIMO, DIAS_MAXIMO) == (1, 3650)
    assert validar(7, 1, 3650) == RetencaoDaAutomacao(7, 1, 3650)
    assert validar(7, None, None) == RetencaoDaAutomacao(7, None, None)
    assert RetencaoDaAutomacao(7) == RetencaoDaAutomacao(7, None, None)


@pytest.mark.parametrize("imagens,logs,trecho", [(0, None, "imagens"), (None, 0, "logs"), (3651, None, "imagens"),
                                                 (None, 3651, "logs"), (-1, 5, "imagens")])
def test_prazo_fora_dos_limites(imagens, logs, trecho) -> None:
    with pytest.raises(PrazoInvalido, match=f"o prazo de {trecho} vai de 1 a 3650 dias"):
        validar(7, imagens, logs)


def test_corte() -> None:
    assert corte(AGORA, None) is None
    assert corte(AGORA, 30) == AGORA - timedelta(days=30)
    assert corte(AGORA, 1) == AGORA - timedelta(days=1)


class _Repo:
    def __init__(self, prazos: list[RetencaoDaAutomacao]) -> None:
        self.prazos = prazos
        self.gravado: list[tuple[RetencaoDaAutomacao, str | None]] = []

    def com_prazo(self):
        return self.prazos

    def obter(self, automation_id):
        return next((x for x in self.prazos if x.automation_id == automation_id), None)

    def gravar(self, retencao, por):
        self.gravado.append((retencao, por))


class _Telemetria:
    def __init__(self, imagens: int = 0, logs: int = 0) -> None:
        self.chamadas: list[tuple[str, int, datetime]] = []
        self.imagens, self.logs = imagens, logs

    def apagar_imagens(self, automation_id, antes_de):
        self.chamadas.append(("imagens", automation_id, antes_de))
        return self.imagens

    def apagar_logs(self, automation_id, antes_de):
        self.chamadas.append(("logs", automation_id, antes_de))
        return self.logs


class _Lista(list):
    def append(self, item):  # type: ignore[override]
        super().append(item)


class _Commit:
    def __init__(self) -> None:
        self.vezes = 0

    def commit(self) -> None:
        self.vezes += 1


def test_aplicar_so_o_que_tem_prazo_e_audita_o_que_apagou() -> None:
    tele, audit, tx = _Telemetria(imagens=3, logs=40), _Lista(), _Commit()
    repo = _Repo([RetencaoDaAutomacao(7, 30, None), RetencaoDaAutomacao(9, None, 90)])
    feito = AplicarRetencao(repo, tele, audit, tx, agora=lambda: AGORA).execute()
    assert tele.chamadas == [("imagens", 7, AGORA - timedelta(days=30)), ("logs", 9, AGORA - timedelta(days=90))]
    assert feito == [
        {"automation_id": 7, "imagens": 3, "linhas_de_log": 0, "imagens_antes_de": (AGORA - timedelta(days=30)).isoformat(), "logs_antes_de": None},
        {"automation_id": 9, "imagens": 0, "linhas_de_log": 40, "imagens_antes_de": None, "logs_antes_de": (AGORA - timedelta(days=90)).isoformat()},
    ]
    assert [(e.action, e.actor_type, e.actor_id, e.resource_type, e.resource_id) for e in audit] == [
        ("retencao.aplicada", "system", None, "automation", "7"), ("retencao.aplicada", "system", None, "automation", "9")]
    assert audit[0].after["imagens_antes_de"] == (AGORA - timedelta(days=30)).isoformat() and audit[0].after["logs_antes_de"] is None
    assert tx.vezes == 2


def test_nada_apagado_nao_audita() -> None:
    tele, audit, tx = _Telemetria(), _Lista(), _Commit()
    feito = AplicarRetencao(_Repo([RetencaoDaAutomacao(7, 30, 30)]), tele, audit, tx, agora=lambda: AGORA).execute()
    assert feito == [] and list(audit) == [] and len(tele.chamadas) == 2 and tx.vezes == 1


def test_sem_prazo_nada_e_consultado() -> None:
    tele = _Telemetria(imagens=99, logs=99)
    assert AplicarRetencao(_Repo([]), tele, _Lista(), _Commit(), agora=lambda: AGORA).execute() == []
    assert tele.chamadas == []


def test_definir_valida_grava_e_audita_o_antes() -> None:
    from types import SimpleNamespace

    repo, audit, tx = _Repo([RetencaoDaAutomacao(7, 10, None)]), _Lista(), _Commit()
    ator = SimpleNamespace(id=5, email="adm@x.com")
    r = DefinirRetencao(repo, audit, tx).execute(ator, 7, 30, 90)
    assert r == RetencaoDaAutomacao(7, 30, 90) and repo.gravado == [(r, "adm@x.com")] and tx.vezes == 1
    e = audit[0]
    assert (e.action, e.actor_type, e.actor_id, e.resource_id) == ("retencao.definida", "user", "5", "7")
    assert e.after == {"imagens_dias": 30, "logs_dias": 90, "antes": {"imagens_dias": 10, "logs_dias": None}}
    with pytest.raises(PrazoInvalido):
        DefinirRetencao(repo, audit, tx).execute(ator, 7, 0, None)
    assert len(repo.gravado) == 1 and tx.vezes == 1
    DefinirRetencao(_Repo([]), audit, tx).execute(SimpleNamespace(id=6), 8, None, 5)
    assert audit[-1].after["antes"] is None


def test_retencao_e_imutavel() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        RetencaoDaAutomacao(7, 1, 1).imagens_dias = 2  # type: ignore[misc]
