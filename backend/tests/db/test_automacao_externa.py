"""Automação externa de ponta a ponta, em HTTP na rede interna (provisório, 11/11/2026).

Portal real (uvicorn) no banco de teste, sem TLS. Cadastro pela API (automação, versão com
o manifesto e publicação sem pacote), pedido pela fila, inscrição e trabalho pelo SDK. A
máquina também tem um Agent online: o job externo vai para a instância direta mesmo assim.
"""

from __future__ import annotations

import json
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
from tests.db.semente import agente

BACKEND = Path(__file__).resolve().parents[2]
SDK = BACKEND.parent / "sdk" / "python"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

from portal_automacoes.instancia import Instancia, trabalhar  # noqa: E402

MANIFESTO = {
    "schema_version": "1.0",
    "automation": {"id": "teste.externa", "name": "Externa de teste", "version": "0.1.0"},
    "runtime": {"id": "python-desktop", "version": "3.12"},
    "entrypoint": {"type": "externa", "comando": "dfolha central trabalhar"},
    "execution": {"mode": "tela"},
    "itens": {"nome": "Empresa", "chave": "codigo",
              "atributos": {"type": "object", "properties": {"codigo": {"type": "string"},
                                                             "separar_por_custo": {"type": "boolean"}}}},
    "etapas": [{"chave": "trocar_empresa", "nome": "Trocar empresa"}],
}


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def portal_http(engine, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("externa")
    porta = _porta_livre()
    ambiente = {**os.environ, "POSTGRES_DB": NOME, "LOCAL_STORAGE_PATH": str(pasta / "storage"),
                "STORAGE_BACKEND": "local", "PYTHONIOENCODING": "utf-8"}
    processo = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(porta)],
                                cwd=BACKEND, env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{porta}"
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{url}/api/v1/health", timeout=2):
                break
        except OSError:
            if processo.poll() is not None:
                pytest.fail(processo.stdout.read().decode(errors="replace")[-3000:])
            time.sleep(0.5)
    else:
        processo.kill()
        pytest.fail("o Portal não subiu")
    yield SimpleNamespace(url=url)
    processo.terminate()
    processo.wait(timeout=20)


def test_automacao_externa_de_ponta_a_ponta_em_http(portal_http, cliente, sessao, tmp_path) -> None:
    from modules.access.api.dependencies import get_current_user

    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email="admin@teste.invalid", role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    sufixo = uuid.uuid4().hex[:6]
    categoria = cliente.post("/api/v1/categories", json={"name": f"Folha {sufixo}", "slug": f"folha-{sufixo}"}).json()["id"]
    chave = f"teste.externa{sufixo}"
    manifesto = {**MANIFESTO, "automation": {**MANIFESTO["automation"], "id": chave}}
    automacao = cliente.post("/api/v1/automations", json={
        "name": f"Externa {sufixo}", "slug": f"externa-{sufixo}", "key": chave, "category_id": categoria,
        "executor_type": "direto"}).json()
    versao = cliente.post(f"/api/v1/automations/{automacao['id']}/versions",
                          json={"raw_manifest": json.dumps(manifesto)})
    assert versao.status_code == 201, versao.text
    publicada = cliente.post(f"/api/v1/automation-versions/{versao.json()['id']}/publish")
    assert publicada.status_code == 200 and publicada.json()["status"] == "published", publicada.text
    version_id = versao.json()["id"]

    # Inscrição em HTTP (provisório): sem permitir_http, é recusada antes de sair da máquina.
    codigo = cliente.post(f"/api/v1/automations/{automacao['id']}/instancias-diretas/codigos").json()["codigo"]
    with pytest.raises(ValueError, match="https"):
        Instancia.inscrever(portal_http.url, codigo=codigo, nome="externa", pasta=tmp_path)
    instancia = Instancia.inscrever(portal_http.url, codigo=codigo, nome="externa", pasta=tmp_path,
                                    nome_maquina="MAQ194", permitir_http=True)
    mch = cliente.post("/api/v1/maquinas", json={"nome": f"MAQ194-{sufixo}"}).json()["id"]
    cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={"maquina_id": mch})
    agente(sessao, mch)  # um Agent online na mesma máquina não pode pegar o job externo
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa' AND id <> :m"), {"m": mch})
    sessao.commit()
    recarregada = Instancia.carregar(tmp_path / "externa.json")
    assert recarregada.permitir_http and recarregada.status()["recebe_jobs"] is True

    # O caminho antigo (direto a um Agent) recusa a automação externa.
    antigo = cliente.post("/api/v1/executions", json={"automation_version_id": version_id, "parameters": {}})
    assert antigo.status_code in (400, 409, 422), antigo.text

    pedido = cliente.post("/api/v1/fila/execucoes", json={
        "automation_version_id": version_id, "itens": [{"chave": "5066", "rotulo": "Empresa 5066"}],
        "parametros": {"competencia": "10/2026"}})
    assert pedido.status_code in (200, 201), pedido.text
    job_id = pedido.json()["jobs"][0]["job_id"]
    entregues = despachar_agora(sessao)["entregues"]
    assert [(e["job_id"], e["modo"]) for e in entregues] == [(job_id, "direto")]

    vistos: list[str] = []

    def executar(job, ambiente):
        from portal_automacoes import Automacao

        vistos.append(job.job_id)
        assert ambiente["PORTAL_PERMITIR_HTTP"] == "1" and job.parametros == {"competencia": "10/2026"}
        with Automacao.conectar(ambiente={**ambiente, "PORTAL_FILA_DIR": str(tmp_path / "fila")}, segundo_plano=True) as a:
            with a.item("5066", rotulo="Empresa 5066"):
                with a.etapa("trocar_empresa"):
                    a.log("Empresa 5066 ativa")

    trabalhar(recarregada, executar, parar=lambda: bool(vistos), avisar=lambda m: None)
    assert vistos == [job_id]

    sessao.expire_all()
    execucao = sessao.execute(text("SELECT execution_id FROM task_executions WHERE id = :j"), {"j": job_id}).scalar_one()
    visao = cliente.get(f"/api/v1/execucoes/{execucao}/acompanhar").json()
    assert visao["jobs"][0]["status"] == "succeeded"
    logs = [l["texto"] for l in cliente.get(f"/api/v1/execucoes/{execucao}/logs").json()["logs"]]
    assert "Empresa 5066 ativa" in logs
    print(f"\nexterna em HTTP: publicada sem pacote; job {job_id} foi para a instância direta (Agent ignorado);"
          f" eventos recebidos; {visao['jobs'][0]['status']}")
