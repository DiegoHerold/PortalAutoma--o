"""SDK 0.4.0: parar e cancelar funcionam em qualquer automação, sem depender de ela consultar.

- cancelar sem tratamento próprio: interrompe na hora;
- com ``ao_cancelar`` (ou consultando ``deve_parar``): prazo para parar sozinha, depois interrompe;
- processo só da execução: encerra o processo depois da interrupção;
- parar depois do item: o próximo item não começa;
- 2 min sem Portal, ou o Portal dizendo que o job acabou (401/409): cancela também;
- ``trabalhar`` segue esperando jobs depois da interrupção do SDK.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

import pytest

import portal_automacoes.automacao as modulo
from portal_automacoes import Automacao, ParadaSolicitada
from portal_automacoes.fila import FilaLocal
from portal_automacoes.instancia import Job, _executar_um
from portal_automacoes.transporte import FalhaDeTransporte, Recusado


def _comando(tipo: str, motivo: str | None = None) -> dict[str, Any]:
    c = {"protocol_version": "automation-events/1", "command_id": f"cmd_{tipo}", "type": tipo,
         "issued_at": "2026-11-12T14:00:00Z"}
    return {**c, "motivo": motivo} if motivo else c


class Portal:
    nome = "direto"

    def __init__(self) -> None:
        self.recebidos: list[dict[str, Any]] = []
        self.comandos_pendentes: list[dict[str, Any]] = []
        self.fora_do_ar = False
        self.recusa: int | None = None
        self.recusados: list = []

    def conectar(self) -> int:
        self._checar()
        return max((e["sequence"] for e in self.recebidos), default=0)

    def _checar(self) -> None:
        if self.fora_do_ar:
            raise FalhaDeTransporte("fora do ar")
        if self.recusa:
            raise Recusado(f"Portal recusou ({self.recusa})", codigo=self.recusa)

    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        self._checar()
        ultima = max((e["sequence"] for e in self.recebidos), default=0)
        self.recebidos += [e for e in eventos if e["sequence"] > ultima]
        return max(e["sequence"] for e in self.recebidos)

    def comandos(self) -> list[dict[str, Any]]:
        self._checar()
        saida, self.comandos_pendentes = self.comandos_pendentes, []
        return saida

    def enviar_imagem(self, *_a: Any) -> None: ...
    def enviar_arquivo(self, *_a: Any) -> None: ...
    def fechar(self) -> None: ...

    def tipos(self) -> list[str]:
        return [e["type"] for e in self.recebidos]

    def textos(self) -> list[str]:
        return [e["payload"].get("texto", "") for e in self.recebidos if e["type"] == "log"]


class Registro:
    def __init__(self) -> None:
        self.interrupcoes = 0
        self.saidas: list[int] = []

    def interromper(self) -> None:
        self.interrupcoes += 1

    def sair(self, codigo: int) -> None:
        self.saidas.append(codigo)


def _automacao(tmp_path: Path, portal: Portal, registro: Registro, **kw: Any) -> Automacao:
    return Automacao(portal, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True,
                     interromper=registro.interromper, encerrar_processo=registro.sair, **kw)


def _esperar(condicao, limite: float = 5.0) -> bool:
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return condicao()


def test_cancelar_sem_tratamento_interrompe_na_hora(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg)
    a.__enter__()
    portal.comandos_pendentes.append(_comando("cancelar", "pedido por Ana"))
    assert _esperar(lambda: reg.interrupcoes == 1)
    assert modulo.interrompida_pelo_sdk() is True and modulo.interrompida_pelo_sdk() is False
    assert _esperar(lambda: any("Cancelamento recebido (pedido por Ana)" in t for t in portal.textos()))
    a.__exit__(KeyboardInterrupt, KeyboardInterrupt(), None)
    fim = next(e for e in portal.recebidos if e["type"] == "execucao.concluida")["payload"]
    assert fim == {"situacao": "interrompida", "resumo": "pedido por Ana"}
    assert reg.saidas == []  # não é processo próprio: nunca encerra o processo


def test_com_ao_cancelar_ela_tem_o_prazo_e_terminando_nao_e_interrompida(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg, prazo_cancelar_s=0.4)
    chamado: list[str] = []
    a.ao_cancelar(lambda: chamado.append("fechar a Domínio"))
    with a:
        portal.comandos_pendentes.append(_comando("cancelar"))
        assert _esperar(lambda: chamado == ["fechar a Domínio"])
        assert reg.interrupcoes == 0  # dentro do prazo
    time.sleep(0.6)
    assert reg.interrupcoes == 0  # terminou sozinha: o prazo foi desarmado


def test_passado_o_prazo_interrompe_e_processo_proprio_e_encerrado(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(modulo, "FOLGA_ENCERRAR_S", 0.2)
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg, prazo_cancelar_s=0.2, processo_proprio=True)
    a.ao_cancelar(lambda: None)  # "trata", mas não para
    a.__enter__()
    a.iniciar_item("5076", rotulo="Filial A")
    portal.comandos_pendentes.append(_comando("cancelar"))
    assert _esperar(lambda: reg.interrupcoes == 1)
    assert _esperar(lambda: reg.saidas == [130])
    tipos = portal.tipos()
    assert tipos[-2:] == ["item.concluido", "execucao.concluida"]
    assert portal.recebidos[-2]["payload"]["situacao"] == "cancelado"
    assert portal.recebidos[-1]["payload"]["situacao"] == "interrompida"


def test_quem_consulta_deve_parar_tambem_ganha_o_prazo(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg, prazo_cancelar_s=30)
    with a:
        a.deve_parar()
        portal.comandos_pendentes.append(_comando("cancelar"))
        assert _esperar(lambda: a.cancelamento_pedido())
        assert reg.interrupcoes == 0


def test_parar_depois_do_item_nao_comeca_o_proximo(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg)
    avisada: list[bool] = []
    a.ao_parar(lambda: avisada.append(True))
    with pytest.raises(ParadaSolicitada):
        with a:
            with a.item("5081"):
                portal.comandos_pendentes.append(_comando("parar_apos_item"))
                assert _esperar(lambda: avisada == [True])
            with a.item("5076"):  # não começa
                raise AssertionError("não deveria começar")
    iniciados = [e["payload"]["item"] for e in portal.recebidos if e["type"] == "item.iniciado"]
    assert iniciados == ["5081"] and reg.interrupcoes == 0
    assert portal.recebidos[-1]["payload"]["situacao"] == "interrompida"


def test_parar_tambem_vale_sem_segundo_plano(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = Automacao(portal, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), interromper=reg.interromper)
    with pytest.raises(ParadaSolicitada):
        with a:
            with a.item("5081"):
                portal.comandos_pendentes.append(_comando("parar_apos_item"))
            with a.item("5076"):
                pass
    assert [e["payload"]["item"] for e in portal.recebidos if e["type"] == "item.iniciado"] == ["5081"]


def test_dois_minutos_sem_portal_cancela_a_execucao(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    log = io.StringIO()
    a = Automacao(portal, FilaLocal(tmp_path / "f.db"), log_local=log, segundo_plano=True, limite_sem_portal_s=0.5,
                  interromper=reg.interromper)
    a.__enter__()
    portal.fora_do_ar = True
    a.log("trabalhando")
    assert _esperar(lambda: reg.interrupcoes == 1, limite=8)
    assert "sem comunicação com o Portal" in log.getvalue() and "tentando por até" in log.getvalue()
    assert a.motivo_da_parada.startswith("sem comunicação com o Portal")
    a.__exit__(KeyboardInterrupt, KeyboardInterrupt(), None)


def test_portal_volta_antes_do_limite_nao_cancela(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = Automacao(portal, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True,
                  limite_sem_portal_s=3, interromper=reg.interromper)
    with a:
        portal.fora_do_ar = True
        a.log("um")
        time.sleep(0.3)
        portal.fora_do_ar = False
        a._fora_do_ar_ate = 0.0
        a._acordar.set()
        assert _esperar(lambda: a._sem_portal_desde is None)
    assert reg.interrupcoes == 0


def test_job_encerrado_no_portal_cancela(tmp_path: Path) -> None:
    portal, reg = Portal(), Registro()
    a = _automacao(tmp_path, portal, reg)
    a.__enter__()
    portal.recusa = 409
    a.log("mais um")
    assert _esperar(lambda: reg.interrupcoes == 1)
    assert a.motivo_da_parada == "o Portal encerrou esta execução"
    a.fechar(tempo_limite_s=0.2)


def test_interrupcao_de_verdade_chega_na_thread_principal(tmp_path: Path) -> None:
    portal = Portal()
    a = Automacao(portal, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True)
    with pytest.raises(KeyboardInterrupt):
        with a:
            portal.comandos_pendentes.append(_comando("cancelar"))
            fim = time.monotonic() + 10
            while time.monotonic() < fim:  # "automação" que nunca consulta nada
                time.sleep(0.05)
    assert modulo.interrompida_pelo_sdk() is True
    assert portal.recebidos[-1]["payload"]["situacao"] == "interrompida"


def test_trabalhar_segue_depois_da_interrupcao_do_sdk_e_de_erro_da_automacao() -> None:
    job = Job("tsk_1", "exe_1", "t", 1, {}, [])
    avisos: list[str] = []

    def interrompida(_job, _amb):
        modulo._interrompeu.set()
        raise KeyboardInterrupt

    _executar_um(interrompida, job, {}, avisos.append)
    _executar_um(lambda _j, _a: 1 / 0, job, {}, avisos.append)
    assert "interrompido pelo SDK" in avisos[0] and "ZeroDivisionError" in avisos[1]
    with pytest.raises(KeyboardInterrupt):  # Ctrl+C de uma pessoa continua saindo
        _executar_um(lambda _j, _a: (_ for _ in ()).throw(KeyboardInterrupt()), job, {}, avisos.append)
