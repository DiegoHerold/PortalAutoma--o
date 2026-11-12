"""Ligação "lisa" de qualquer automação: HTTP provisório só na rede interna, envio em
segundo plano (o robô nunca espera a rede) e o arquivo do job."""

from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path

import pytest

from portal_automacoes import Automacao, job_atual
from portal_automacoes import eventos as ev
from portal_automacoes.enderecos import endereco_interno, validar_url_portal
from portal_automacoes.fila import FilaLocal
from portal_automacoes.instancia import Job
from portal_automacoes.transporte import FalhaDeTransporte
from portal_automacoes.transporte_direto import TransporteDireto
from portal_automacoes.trabalhador import gravar_job
from simuladores.portal_simulado import PortalSimulado


@pytest.mark.parametrize("host,interno", [
    ("127.0.0.1", True), ("192.168.1.109", True), ("10.0.0.5", True), ("172.16.3.4", True),
    ("MAQ65", True), ("maq65.intranet.biason.net", True), ("portal.local", True),
    ("8.8.8.8", False), ("portal.biason.net", False), ("exemplo.com", False),
])
def test_endereco_interno(host: str, interno: bool) -> None:
    assert endereco_interno(host) is interno


def test_http_so_com_permissao_explicita_e_so_na_rede_interna() -> None:
    assert validar_url_portal("https://portal.biason.net/") == "https://portal.biason.net"
    with pytest.raises(ValueError, match="só aceita https"):
        validar_url_portal("http://192.168.1.109:8000")
    assert validar_url_portal("http://192.168.1.109:8000", permitir_http=True) == "http://192.168.1.109:8000"
    with pytest.raises(ValueError, match="rede interna"):
        validar_url_portal("http://portal.biason.net", permitir_http=True)
    with pytest.raises(ValueError, match="credenciais"):
        validar_url_portal("http://u:s@192.168.1.109", permitir_http=True)
    with pytest.raises(ValueError, match="https"):
        validar_url_portal("ftp://192.168.1.109", permitir_http=True)


@pytest.fixture
def portal_http():
    with PortalSimulado(None, None, ev.validar) as p:
        p.criar_job("job_a", "token-do-job-a")
        yield p


def test_modo_direto_em_http_na_rede_interna(portal_http: PortalSimulado, tmp_path: Path) -> None:
    ambiente = {"PORTAL_MODO": "direto", "PORTAL_URL": portal_http.url, "PORTAL_JOB_ID": "job_a",
                "PORTAL_JOB_TOKEN": "token-do-job-a", "PORTAL_FILA_DIR": str(tmp_path)}
    with pytest.raises(ValueError, match="https"):
        Automacao.conectar(ambiente=ambiente)  # sem permissão explícita, http é recusado
    with Automacao.conectar(ambiente={**ambiente, "PORTAL_PERMITIR_HTTP": "1"}) as a:
        a.log("pela rede interna, sem TLS")
    assert [e["type"] for e in portal_http.jobs["job_a"].eventos] == ["execucao.iniciada", "log", "execucao.concluida"]


class _Lento:
    """Portal que demora a responder (ou está fora do ar)."""

    nome = "direto"

    def __init__(self, atraso: float, fora: bool = False, com_comando: bool = False) -> None:
        self.atraso, self.fora, self.com_comando = atraso, fora, com_comando
        self.recebidos: list[int] = []
        self.recusados: list = []

    def conectar(self) -> int:
        time.sleep(self.atraso)
        if self.fora:
            raise FalhaDeTransporte("fora do ar")
        return max(self.recebidos, default=0)

    def enviar(self, eventos):
        time.sleep(self.atraso)
        if self.fora:
            raise FalhaDeTransporte("fora do ar")
        self.recebidos += [e["sequence"] for e in eventos]
        return max(self.recebidos)

    def comandos(self):
        if self.fora:
            raise FalhaDeTransporte("fora do ar")
        return [{"protocol_version": "automation-events/1", "command_id": "cmd_1", "type": "parar_apos_item",
                 "issued_at": "2026-11-11T10:00:00Z"}] if self.recebidos and self.com_comando else []

    def enviar_imagem(self, imagem_id, jpeg):
        raise AssertionError("não chega aqui")

    def fechar(self):
        return None


def test_segundo_plano_quem_emite_nao_espera_a_rede(tmp_path: Path) -> None:
    lento = _Lento(atraso=0.5, fora=True, com_comando=True)
    a = Automacao(lento, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True)
    inicio = time.monotonic()
    a.iniciar_item("5081", rotulo="Matriz")
    for i in range(50):
        a.log(f"linha {i}")
    a.concluir_item()
    assert time.monotonic() - inicio < 0.5  # 52 eventos sem esperar o Portal (fora do ar)
    assert a.pendentes == 52 and lento.recebidos == []
    lento.fora, lento.atraso = False, 0.0  # Portal de volta
    a._fora_do_ar_ate = 0.0
    a._acordar.set()
    limite = time.monotonic() + 5
    while lento.recebidos[-1:] != [52] and time.monotonic() < limite:
        time.sleep(0.05)
    assert lento.recebidos[:52] == list(range(1, 53))
    limite = time.monotonic() + 5
    while not a.deve_parar() and time.monotonic() < limite:  # comando lido pela thread de envio
        time.sleep(0.05)
    assert a.deve_parar()
    a.fechar()
    assert a.pendentes == 0


def test_segundo_plano_fechar_esvazia_a_fila(tmp_path: Path) -> None:
    lento = _Lento(atraso=0.0)
    with Automacao(lento, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True) as a:
        for i in range(10):
            a.log(f"linha {i}")
    assert lento.recebidos == list(range(1, 13)) and a.pendentes == 0


def test_segundo_plano_varias_threads_sem_repetir_sequencia(tmp_path: Path) -> None:
    lento = _Lento(atraso=0.001)
    a = Automacao(lento, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True)

    def emitir(n: int) -> None:
        for i in range(40):
            a.log(f"t{n} {i}")

    threads = [threading.Thread(target=emitir, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    a.fechar()
    assert sorted(lento.recebidos) == list(range(1, 161)) and len(set(lento.recebidos)) == 160


def test_imagem_com_portal_fora_do_ar_nao_segura_o_passo(tmp_path: Path) -> None:
    lento = _Lento(atraso=0.0, fora=True)
    a = Automacao(lento, FilaLocal(tmp_path / "f.db"), log_local=io.StringIO(), segundo_plano=True)
    a._fora_do_ar_ate = time.monotonic() + 30
    a.passo("Abriu: Rubricas", imagem=b"qualquer")  # não tenta enviar: entra só o texto
    evento = json.loads(json.dumps(a._fila.pendentes()[-1]))
    assert evento["type"] == "passo" and evento["payload"].get("imagem_id") is None
    a.fechar(tempo_limite_s=0.5)


def test_arquivo_do_job(tmp_path: Path) -> None:
    job = Job("tsk_1", "exe_1", "token-secreto", 1, {"competencia": "10/2026"},
              [{"chave": "5081", "rotulo": "Matriz", "grupo": None, "atributos": {"separar_por_custo": True}}])
    arquivo = gravar_job(job, tmp_path)
    dados = job_atual({"PORTAL_JOB_ARQUIVO": str(arquivo)})
    assert dados["parametros"] == {"competencia": "10/2026"} and dados["itens"][0]["chave"] == "5081"
    assert "token-secreto" not in arquivo.read_text(encoding="utf-8")  # o token não vai para o disco
    assert job_atual({}) == {"parametros": {}, "itens": []}
