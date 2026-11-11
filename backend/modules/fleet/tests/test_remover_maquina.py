"""Apagar uma máquina: rodando não apaga; com vínculos, só confirmando; sem vínculos, direto."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from modules.fleet.application.remover_maquina import (
    MaquinaNaoEncontrada,
    MaquinaOcupada,
    PrecisaConfirmar,
    RemoverMaquina,
    tem_vinculos,
)

AGORA = datetime(2026, 11, 11, 16, 0, tzinfo=UTC)


class _Maquinas:
    def __init__(self, automacoes=(), agents=()) -> None:
        self.maquina = SimpleNamespace(id="mch_1", name="MAQ194")
        self.automacoes, self.agents = list(automacoes), list(agents)
        self.chamadas: list[tuple] = []

    def obter(self, machine_id):
        return self.maquina if machine_id == "mch_1" and not any(c[0] == "removida" for c in self.chamadas) else None

    def instancias_na_maquina(self, machine_id):
        return self.automacoes

    def agents_na_maquina(self, machine_id):
        return self.agents

    def desvincular(self, machine_id):
        self.chamadas.append(("desvincular", machine_id))

    def marcar_removida(self, machine_id, agora):
        self.chamadas.append(("removida", machine_id, agora))


class _Uso:
    def __init__(self, rodando=0, fila=0) -> None:
        self._rodando, self._fila, self.liberadas = rodando, fila, []

    def rodando(self, machine_id):
        return self._rodando

    def na_fila_exigindo(self, machine_id):
        return self._fila

    def liberar(self, machine_id):
        self.liberadas.append(machine_id)
        return self._fila


class _Commit:
    def __init__(self) -> None:
        self.vezes = 0

    def commit(self):
        self.vezes += 1


AUTOMACAO = {"instancia_id": "dri_1", "automation_id": 1, "automacao": "Folha", "situacao": "aprovada"}


def _caso(maquinas, uso):
    audit, tx = [], _Commit()
    return RemoverMaquina(maquinas, uso, audit, tx, agora=lambda: AGORA), audit, tx


def test_sem_vinculos_apaga_direto_e_audita() -> None:
    maquinas, uso = _Maquinas(), _Uso()
    caso, audit, tx = _caso(maquinas, uso)
    assert caso.execute("5", "mch_1", confirmar=False) == {
        "id": "mch_1", "nome": "MAQ194", "automacoes_sem_maquina": 0, "agents_sem_maquina": 0, "jobs_liberados": 0}
    assert maquinas.chamadas == [("desvincular", "mch_1"), ("removida", "mch_1", AGORA)] and uso.liberadas == ["mch_1"]
    (e,) = audit
    assert (e.action, e.actor_id, e.resource_type, e.resource_id) == ("maquina.removida", "5", "machine", "mch_1")
    assert e.before == {"nome": "MAQ194", "automacoes": [], "agents": []} and e.after == {"jobs_liberados": 0, "confirmado": False}
    assert tx.vezes == 1


@pytest.mark.parametrize("maquinas,uso", [
    (_Maquinas(automacoes=[AUTOMACAO]), _Uso()),
    (_Maquinas(agents=[{"id": "agt_1", "nome": "Local"}]), _Uso()),
    (_Maquinas(), _Uso(fila=2)),
])
def test_com_vinculo_pede_confirmacao_e_nao_mexe_em_nada(maquinas, uso) -> None:
    caso, audit, tx = _caso(maquinas, uso)
    with pytest.raises(PrecisaConfirmar) as exc:
        caso.execute("5", "mch_1", confirmar=False)
    assert exc.value.vinculos["maquina"] == {"id": "mch_1", "nome": "MAQ194"}
    assert maquinas.chamadas == [] and uso.liberadas == [] and audit == [] and tx.vezes == 0


def test_confirmado_desvincula_libera_a_fila_e_conta() -> None:
    maquinas, uso = _Maquinas(automacoes=[AUTOMACAO], agents=[{"id": "agt_1", "nome": "Local"}]), _Uso(fila=3)
    caso, audit, _ = _caso(maquinas, uso)
    saida = caso.execute("5", "mch_1", confirmar=True)
    assert saida == {"id": "mch_1", "nome": "MAQ194", "automacoes_sem_maquina": 1, "agents_sem_maquina": 1, "jobs_liberados": 3}
    assert audit[0].before["automacoes"] == [{"instancia_id": "dri_1", "automation_id": 1, "situacao": "aprovada"}]
    assert audit[0].before["agents"] == ["agt_1"] and audit[0].after == {"jobs_liberados": 3, "confirmado": True}


def test_rodando_nunca_apaga_nem_confirmando() -> None:
    maquinas = _Maquinas()
    caso, audit, _ = _caso(maquinas, _Uso(rodando=1))
    with pytest.raises(MaquinaOcupada, match="1 execução"):
        caso.execute("5", "mch_1", confirmar=True)
    assert maquinas.chamadas == [] and audit == []


def test_maquina_inexistente_ou_ja_apagada() -> None:
    caso, _, _ = _caso(_Maquinas(), _Uso())
    with pytest.raises(MaquinaNaoEncontrada):
        caso.vinculos("mch_x")
    caso.execute("5", "mch_1", confirmar=False)
    with pytest.raises(MaquinaNaoEncontrada):
        caso.execute("5", "mch_1", confirmar=True)


def test_tem_vinculos() -> None:
    base = {"automacoes": [], "agents": [], "fila": 0}
    assert not tem_vinculos(base)
    assert tem_vinculos({**base, "automacoes": [AUTOMACAO]})
    assert tem_vinculos({**base, "agents": [{}]})
    assert tem_vinculos({**base, "fila": 1})
