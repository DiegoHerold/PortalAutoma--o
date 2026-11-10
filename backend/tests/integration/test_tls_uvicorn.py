"""O uvicorn com os mesmos parâmetros do scripts/portal.ps1 (--ssl-certfile/--ssl-keyfile):
aceita TLS 1.2 e 1.3 com certificado validado pela CA, recusa TLS 1.1 e HTTP puro."""

from __future__ import annotations

import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
# Mesmo valor de $tlsCiphers em scripts/portal.ps1.
CIFRAS = "ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!eNULL:!MD5:!DSS"
if str(RAIZ / "sdk" / "python") not in sys.path:
    sys.path.insert(0, str(RAIZ / "sdk" / "python"))

from simuladores import certificados  # noqa: E402

APP = '''
async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})
'''


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor(tmp_path_factory: pytest.TempPathFactory):
    pasta = tmp_path_factory.mktemp("tls")
    ca, cert, chave = certificados.gerar(pasta, "localhost")
    (pasta / "app_tls.py").write_text(APP, encoding="utf-8")
    porta = _porta_livre()
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app_tls:app", "--host", "127.0.0.1", "--port", str(porta),
         "--ssl-certfile", str(cert), "--ssl-keyfile", str(chave), "--ssl-ciphers", CIFRAS, "--log-level", "warning"],
        cwd=pasta, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    limite = time.monotonic() + 20
    while time.monotonic() < limite:
        try:
            socket.create_connection(("127.0.0.1", porta), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.2)
    yield porta, ca
    processo.terminate()
    processo.wait(10)


def _handshake(porta: int, ca: Path, maximo: ssl.TLSVersion | None = None, minimo: ssl.TLSVersion | None = None,
               cifras: str | None = None) -> str:
    contexto = ssl.create_default_context(cafile=str(ca))
    if cifras:
        contexto.set_ciphers(cifras)
    if minimo:
        contexto.minimum_version = minimo
    if maximo:
        contexto.maximum_version = maximo
    with socket.create_connection(("127.0.0.1", porta), timeout=5) as bruto:
        with contexto.wrap_socket(bruto, server_hostname="127.0.0.1") as tls:
            return tls.version()


def test_tls_12_aceito_com_certificado_validado(servidor) -> None:
    porta, ca = servidor
    versao = _handshake(porta, ca, maximo=ssl.TLSVersion.TLSv1_2)
    print(f"\nTLS 1.2 forçado no cliente: {versao}")
    assert versao == "TLSv1.2"


def test_tls_13_aceito(servidor) -> None:
    porta, ca = servidor
    assert _handshake(porta, ca) == "TLSv1.3"


def test_tls_11_recusado_pelo_servidor(servidor) -> None:
    """O cliente aqui é capaz de TLS 1.1 (nível de segurança 0): a recusa vem do servidor."""
    porta, ca = servidor
    with pytest.raises((ssl.SSLError, ConnectionError, OSError)) as erro:
        _handshake(porta, ca, minimo=ssl.TLSVersion.TLSv1_1, maximo=ssl.TLSVersion.TLSv1_1, cifras="DEFAULT:@SECLEVEL=0")
    assert "NO_CIPHERS_AVAILABLE" not in str(erro.value), "o cliente não chegou a oferecer TLS 1.1"
    print(f"\nTLS 1.1 oferecido pelo cliente: recusado ({erro.value.__class__.__name__}: {erro.value})")


def test_certificado_validado_pela_ca_responde(servidor) -> None:
    porta, ca = servidor
    contexto = ssl.create_default_context(cafile=str(ca))
    with urllib.request.urlopen(f"https://127.0.0.1:{porta}/health", context=contexto, timeout=5) as resposta:
        assert resposta.read() == b"ok"


def test_ca_desconhecida_e_recusada_pelo_cliente(servidor) -> None:
    porta, _ = servidor
    with pytest.raises(ssl.SSLCertVerificationError):
        with socket.create_connection(("127.0.0.1", porta), timeout=5) as bruto:
            ssl.create_default_context().wrap_socket(bruto, server_hostname="127.0.0.1")


def test_http_puro_nao_e_atendido(servidor) -> None:
    porta, _ = servidor
    with pytest.raises(Exception):  # noqa: B017 - qualquer falha serve: o importante é não responder em texto puro
        urllib.request.urlopen(f"http://127.0.0.1:{porta}/health", timeout=5).read()
