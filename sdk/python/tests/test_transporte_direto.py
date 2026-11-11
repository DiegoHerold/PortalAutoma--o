"""Modo direto contra um Portal simulado em HTTPS de verdade (CA própria do teste)."""

from __future__ import annotations

import io
import ssl
from pathlib import Path

import pytest

from portal_automacoes import Automacao
from portal_automacoes import eventos as ev
from portal_automacoes.fila import FilaLocal
from portal_automacoes.transporte import FalhaDeTransporte, Recusado
from portal_automacoes.transporte_direto import TransporteDireto
from simuladores import certificados
from simuladores.portal_simulado import PortalSimulado


@pytest.fixture
def tls(tmp_path: Path) -> tuple[Path, Path, Path]:
    return certificados.gerar(tmp_path / "tls")


@pytest.fixture
def portal(tls: tuple[Path, Path, Path]):
    _, cert, chave = tls
    with PortalSimulado(cert, chave, ev.validar) as p:
        p.criar_job("job_a", "token-do-job-a")
        p.criar_job("job_b", "token-do-job-b")
        yield p


def test_so_aceita_https() -> None:
    with pytest.raises(ValueError, match="https"):
        TransporteDireto("http://portal.intranet", "job_a", "t")  # sem permitir_http


def test_url_com_credencial_ou_parametro_e_recusada() -> None:
    with pytest.raises(ValueError, match="credenciais"):
        TransporteDireto("https://usuario:senha@portal.intranet", "job_a", "t")
    with pytest.raises(ValueError, match="credenciais"):
        TransporteDireto("https://portal.intranet/?token=abc", "job_a", "t")


def test_tls_minimo_e_validacao_sempre_ligada() -> None:
    transporte = TransporteDireto("https://portal.intranet", "job_a", "t")
    assert transporte._tls.minimum_version == ssl.TLSVersion.TLSv1_2
    assert transporte._tls.verify_mode == ssl.CERT_REQUIRED
    assert transporte._tls.check_hostname is True


def test_certificado_de_ca_desconhecida_nao_conecta(portal: PortalSimulado) -> None:
    transporte = TransporteDireto(portal.url, "job_a", "token-do-job-a")  # sem a CA do teste
    with pytest.raises(FalhaDeTransporte, match="SSL|CERTIFICATE|certificate"):
        transporte.conectar()


def test_envio_com_a_ca_da_empresa(portal: PortalSimulado, tls: tuple[Path, Path, Path]) -> None:
    transporte = TransporteDireto(portal.url, "job_a", "token-do-job-a", str(tls[0]))
    assert transporte.conectar() == 0
    eventos = [ev.montar(n, "log", {"nivel": "info", "texto": f"linha {n}"}) for n in (1, 2, 3)]

    assert transporte.enviar(eventos) == 3
    assert transporte.enviar(eventos) == 3  # reenvio idempotente
    assert [e["sequence"] for e in portal.jobs["job_a"].eventos] == [1, 2, 3]


def test_token_de_outro_job_e_recusado(portal: PortalSimulado, tls: tuple[Path, Path, Path]) -> None:
    transporte = TransporteDireto(portal.url, "job_b", "token-do-job-a", str(tls[0]))
    with pytest.raises(Recusado, match="401"):
        transporte.enviar([ev.montar(1, "log", {"nivel": "info", "texto": "x"})])
    assert portal.jobs["job_b"].eventos == []
    assert portal.recusas_autenticacao == 1


def test_evento_recusado_nao_descarta_os_validos_do_lote(portal: PortalSimulado, tls: tuple[Path, Path, Path]) -> None:
    transporte = TransporteDireto(portal.url, "job_a", "token-do-job-a", str(tls[0]))
    ruim = ev.montar(2, "log", {"nivel": "info", "texto": "x"})
    ruim["payload"]["nivel"] = "verbose"  # adulterado depois da validação local
    lote = [ev.montar(1, "log", {"nivel": "info", "texto": "a"}), ruim, ev.montar(3, "log", {"nivel": "info", "texto": "c"})]

    assert transporte.enviar(lote) == 3
    assert [e["sequence"] for e in portal.jobs["job_a"].eventos] == [1, 3]
    assert [r["sequence"] for r in transporte.recusados] == [2]


def test_automacao_no_modo_direto_com_portal_fora_do_ar_e_depois_de_volta(
        portal: PortalSimulado, tls: tuple[Path, Path, Path], tmp_path: Path) -> None:
    porta_errada = TransporteDireto("https://127.0.0.1:1", "job_a", "token-do-job-a", str(tls[0]), tempo_limite_s=2)
    fila = tmp_path / "fila.db"
    a = Automacao(porta_errada, FilaLocal(fila), log_local=io.StringIO())
    with a:
        a.log("enquanto o Portal está fora")
    assert a.pendentes == 3

    certo = TransporteDireto(portal.url, "job_a", "token-do-job-a", str(tls[0]))
    b = Automacao(certo, FilaLocal(fila), log_local=io.StringIO())
    with b:
        b.log("Portal de volta")
    assert [e["sequence"] for e in portal.jobs["job_a"].eventos] == [1, 2, 3, 4, 5, 6]
    assert b.pendentes == 0
