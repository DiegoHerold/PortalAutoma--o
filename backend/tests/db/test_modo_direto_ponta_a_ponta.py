"""Modo direto de ponta a ponta, como a Integração Contábil vai rodar na máquina .194.

Portal real (uvicorn) em HTTPS com uma CA de teste, no banco de teste. O SDK se inscreve,
espera a aprovação, abre a sessão por desafio assinado, recebe o job, manda eventos e a
imagem do passo, e encerra. Nada de servidor simulado: é o mesmo código que vai rodar.
"""

from __future__ import annotations

import io
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from modules.dispatch.api.fila import despachar_agora
from tests.db.conftest import NOME
from tests.db.semente import automacao, publicar

BACKEND = Path(__file__).resolve().parents[2]
SDK = BACKEND.parent / "sdk" / "python"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

from portal_automacoes import Automacao  # noqa: E402
from portal_automacoes.instancia import Instancia, contexto_tls  # noqa: E402
from simuladores import certificados  # noqa: E402


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def portal_https(engine, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("tls")
    ca, cert, chave = certificados.gerar(pasta, "localhost")
    porta = _porta_livre()
    ambiente = {**os.environ, "POSTGRES_DB": NOME, "LOCAL_STORAGE_PATH": str(pasta / "storage"),
                "STORAGE_BACKEND": "local", "PYTHONIOENCODING": "utf-8"}
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(porta),
         "--ssl-certfile", str(cert), "--ssl-keyfile", str(chave)],
        cwd=BACKEND, env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"https://localhost:{porta}"
    tls = contexto_tls(str(ca))
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{url}/api/v1/health", timeout=2, context=tls):
                break
        except OSError:
            if processo.poll() is not None:
                pytest.fail(processo.stdout.read().decode(errors="replace")[-3000:])
            time.sleep(0.5)
    else:
        processo.kill()
        pytest.fail("o Portal não subiu em HTTPS")
    yield SimpleNamespace(url=url, ca=str(ca), pasta=pasta)
    processo.terminate()
    processo.wait(timeout=20)


def _jpeg() -> bytes:
    from PIL import Image, ImageDraw

    imagem = Image.new("RGB", (800, 450), (230, 236, 244))
    ImageDraw.Draw(imagem).rectangle([40, 40, 760, 410], outline=(20, 40, 70), width=4)
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=80)
    return saida.getvalue()


def test_integracao_pelo_modo_direto_de_ponta_a_ponta(portal_https, cliente, sessao, tmp_path) -> None:
    from modules.access.api.dependencies import get_current_user

    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    codigo = cliente.post(f"/api/v1/automations/{automation_id}/instancias-diretas/codigos").json()["codigo"]

    # Na máquina: inscrição por HTTPS validado pela CA; a chave privada fica no DPAPI.
    instancia = Instancia.inscrever(portal_https.url, codigo=codigo, nome="integracao-contabil",
                                    arquivo_ca=portal_https.ca, nome_maquina="MAQ194", pasta=tmp_path)
    assert instancia.status()["status"] == "pendente"
    credencial = (tmp_path / "integracao-contabil.json").read_text(encoding="utf-8")
    assert "BEGIN" not in credencial and "PRIVATE" not in credencial  # só o blob do DPAPI

    # No Portal: máquina cadastrada e instância aprovada nela.
    mch = cliente.post("/api/v1/maquinas", json={"nome": f"MAQ194-{uuid.uuid4().hex[:4]}"}).json()["id"]
    cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={"maquina_id": mch})
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa' AND id <> :m"), {"m": mch})
    sessao.commit()

    recarregada = Instancia.carregar(tmp_path / "integracao-contabil.json")  # como depois de reiniciar a máquina
    assert recarregada.status() == {"instancia_id": instancia.id, "status": "aprovada", "maquina_id": mch, "recebe_jobs": True}

    pedido = cliente.post("/api/v1/fila/execucoes", json={
        "automation_version_id": version_id, "itens": [{"chave": "5066", "rotulo": "Empresa 5066"}],
        "parametros": {"competencia": "10/2026", "modo": "completo"}})
    job_id = pedido.json()["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [job_id]

    job = recarregada.proximo_job(espera=5)
    assert job is not None and job.job_id == job_id and job.parametros["competencia"] == "10/2026"

    ambiente = {**recarregada.ambiente_do_job(job), "PORTAL_FILA_DIR": str(tmp_path / "fila")}
    with Automacao.conectar(versao_automacao="2.0.0", ambiente=ambiente) as automacao_sdk:
        with automacao_sdk.item("5066", rotulo="Empresa 5066"):
            with automacao_sdk.etapa("trocar_empresa"):
                automacao_sdk.passo("Trocou para a empresa 5066", imagem=_jpeg())
                automacao_sdk.log("Empresa 5066 ativa na barra de status")
        automacao_sdk.resumo("1 empresa integrada")

    # O Portal viu tudo: imagem pronta, job concluído e a máquina livre de novo.
    sessao.expire_all()
    visao = cliente.get(f"/api/v1/execucoes/{job.execucao_id}/acompanhar").json()
    assert visao["agora"]["tela"]["imagem"] == {"situacao": "pronta", "motivo": None}
    assert visao["jobs"][0]["status"] == "succeeded" and visao["jobs"][0]["maquina_nome"].startswith("MAQ194")
    logs = cliente.get(f"/api/v1/execucoes/{job.execucao_id}/logs").json()["logs"]
    assert "Empresa 5066 ativa na barra de status" in [l["texto"] for l in logs]
    travas = sessao.execute(text("SELECT count(*) FROM resource_locks WHERE machine_id = :m AND status = 'active'"),
                            {"m": mch}).scalar_one()
    assert travas == 0
    print(f"\nponta a ponta (HTTPS + CA validada): inscrição -> aprovação em {mch} -> job {job_id} -> eventos e "
          f"imagem -> {visao['jobs'][0]['status']}; tela {visao['agora']['tela']['imagem_id']} pronta; máquina livre")
