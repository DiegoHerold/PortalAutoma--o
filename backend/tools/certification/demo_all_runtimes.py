"""
Demonstracao real, multi-runtime: para cada tipo de entrypoint que o Agent
suporta em background (python_function, powershell_script, executable),
cria/publica uma automacao real no catalogo do Portal (mesma API HTTP que o
frontend usa) e dispara uma execucao real contra o Agent conectado -
reportando pass/fail genuino por runtime, no mesmo processo, em uma unica
rodada.

Isso prova de fato o que foi corrigido nesta sessao:
  - powershell_script e executable agora rodam sem exigir uma entrada no
    Runtime Store (ExecutionManager.cs) - eles usam binarios ja instalados
    na maquina / empacotados dentro do pacote, nao um runtime baixado.
  - o bug que fazia toda automacao "executable" falhar com "Executable
    entrypoint requires 'executable_path'" foi corrigido
    (ProcessTreeManager.WriteConfigFileAsync nao mandava mais o path pro
    ExecutionHost).
  - "powershell-core"/"dotnet-runtime" (runtime.id invalidos nos exemplos)
    viraram "powershell"/"executable" (os IDs que o ManifestValidator aceita).

Roda de dentro do container do backend:
  docker compose exec -T backend python -m tools.certification.demo_all_runtimes 2>/dev/null \
  || docker compose cp demo_all_runtimes.py <backend_container>:/app/demo_all_runtimes.py \
  && docker compose exec -T backend python /app/demo_all_runtimes.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid

import yaml

from tools.certification.api_client import PortalApiClient, PortalApiError
from tools.certification.packaging import build_package_zip
from tools.certification.execution import wait_until_terminal, ExecutionTimeoutError

PORTAL_API_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")

CATEGORY_NAME = "Biason Demo"
CATEGORY_SLUG = "biason-demo"

# 1.0.0 foi usado numa rodada anterior que caiu nos bugs reais do
# validador de pacotes do Portal (corrigidos nesta sessao: extensao
# .ps1/.exe bloqueada incondicionalmente, e o caminho esperado do
# entrypoint python-function com prefixo "application/" fixo e errado).
# Essas versoes ficaram em status "blocked" no Portal, que e imutavel
# (nao aceita novo upload nem publicacao) - por isso usamos uma versao
# nova para a rodada corrigida em vez de tentar reaproveitar 1.0.0.
DEMO_VERSION = "1.0.1"

RUNTIME_SPECS = [
    {
        "key": "demo.biason_fiscal",
        "name": "Biason - Demo Processamento Fiscal (python_function)",
        "slug": "biason-demo-processamento-fiscal",
        "package_source_dir": "/certification-packages/demo_fiscal",
        "runtime": {"id": "python-core", "version": "3.13"},
        "runtime_name": "Python Core",
        "entrypoint": {"type": "python-function", "module": "automation.main", "function": "run"},
        "capabilities": ["windows", "agent.background_execution"],
        "parameters": {
            "documentos": [
                "nota_fiscal_1234.xml",
                "guia_das_agosto_2026.pdf",
                "folha_pagamento_agosto.pdf",
                "certidao_negativa_receita.pdf",
                "contrato_cliente_042.pdf",
            ]
        },
    },
    {
        "key": "demo.biason_powershell",
        "name": "Biason - Demo PowerShell (powershell_script)",
        "slug": "biason-demo-powershell",
        "package_source_dir": "/certification-packages/demo_powershell",
        "runtime": {"id": "powershell", "version": "system"},
        "runtime_name": "PowerShell (instalado na maquina)",
        "entrypoint": {"type": "powershell-script", "script": "automation/main.ps1"},
        "capabilities": ["windows", "agent.background_execution"],
        "parameters": {
            "documentos": [
                "certidao_negativa_federal.pdf",
                "certidao_negativa_estadual.pdf",
                "certidao_negativa_municipal.pdf",
                "certidao_fgts.pdf",
                "certidao_trabalhista.pdf",
            ]
        },
    },
    {
        "key": "demo.biason_executable",
        "name": "Biason - Demo Executavel (executable)",
        "slug": "biason-demo-executavel",
        "package_source_dir": "/certification-packages/demo_executable",
        "runtime": {"id": "executable", "version": "1.0"},
        "runtime_name": "Executavel empacotado (.NET)",
        "entrypoint": {"type": "executable", "path": "automation/ExampleTool.exe"},
        "capabilities": ["windows", "agent.background_execution"],
        "parameters": {
            "contratos": [
                "contrato_cliente_001.pdf",
                "contrato_cliente_002.pdf",
                "contrato_cliente_003.pdf",
                "termo_confidencialidade_2026.pdf",
            ]
        },
    },
    {
        # 4o runtime: navegador real via Playwright. So chega a rodar de
        # verdade se (a) o Agent.Service tiver BrowserPoolSize > 0
        # (appsettings.Certification.json - corrigido nesta rodada, era 0)
        # e (b) existir de fato uma pasta
        # certification-runs/agent-data/store/runtimes/python-browser-3.13-playwright
        # com um python.exe + playwright instalado + Chromium baixado em
        # "browsers/" (RuntimeStore so verifica Directory.Exists - ver
        # provision-browser-runtime.ps1). Sem isso o Agent falha ANTES de
        # lancar o processo com "Runtime not found: python-browser:3.13-playwright".
        "key": "demo.biason_browser",
        "name": "Biason - Demo Navegador (browser_playwright)",
        "slug": "biason-demo-navegador",
        "package_source_dir": "/certification-packages/demo_browser",
        "runtime": {"id": "python-browser", "version": "3.13-playwright"},
        "runtime_name": "Python + Playwright (Chromium)",
        "entrypoint": {"type": "browser-playwright", "module": "automation.main", "function": "run"},
        "capabilities": ["windows", "agent.browser_execution"],
        "parameters": {
            # headless=True roda invisivel (uso normal). Pra ver o Chromium
            # abrindo na tela de verdade, rode manualmente com
            # {"headless": false} E execution.mode="interactive" no
            # automation.json (senao o Agent esconde a janela por design -
            # ver RuntimeLauncher.CreateBase).
            "headless": True,
        },
    },
]


def build_raw_manifest(spec: dict) -> str:
    document = {
        "schema_version": 1,
        "id": spec["key"],
        "name": spec["name"],
        "version": DEMO_VERSION,
        "description": f"Demonstracao real do entrypoint {spec['entrypoint']['type']} no Automation Agent.",
        "category": CATEGORY_SLUG,
        "runtime": spec["runtime"],
        "entrypoint": spec["entrypoint"],
        "execution": {"mode": "background", "timeout_seconds": 120, "graceful_cancellation_seconds": 10},
        "resources": {"cpu_units": 1, "memory_mb": 256, "disk_mb": 100},
        "capabilities": {"required": spec["capabilities"]},
    }
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def _ensure_runtime_published(client: PortalApiClient, spec: dict) -> dict:
    # O Portal mantem seu PROPRIO catalogo de Runtime/RuntimeVersion
    # (tabelas separadas do Runtime Store local do Agent) e so deixa
    # publicar uma AutomationVersion se existir uma RuntimeVersion
    # correspondente ja publicada (PublishAutomationVersion.execute checa
    # find_runtime_version(runtime_id, runtime_version).status ==
    # "published"). E um passo de onboarding real do runtime no catalogo,
    # nao um bug - mas so python-core/3.13 tinha sido registrado ate agora
    # (pelo seed da certificacao). Registramos/publicamos aqui os runtimes
    # novos (powershell/system, executable/1.0) do mesmo jeito que o seed
    # da certificacao ja faz para python-core.
    runtime_id = spec["runtime"]["id"]
    runtime_version = spec["runtime"]["version"]
    runtime = client.get_or_create_runtime(runtime_id, spec.get("runtime_name", runtime_id))

    # get_or_create_runtime ja retorna as versoes existentes embutidas
    # (RuntimeResponse.versions) - evita uma chamada GET extra.
    existing = next((v for v in runtime.get("versions", []) if v.get("version") == runtime_version), None)
    if existing is not None:
        version = existing
    else:
        version = client.create_runtime_version(
            runtime["id"],
            runtime_version,
            supported_entrypoints=[spec["entrypoint"]["type"]],
        )

    if version.get("status") != "published":
        version = client.publish_runtime_version(version["id"])
        print(f"RuntimeVersion {runtime_id}:{runtime_version} publicada (id={version['id']}).")
    else:
        print(f"RuntimeVersion {runtime_id}:{runtime_version} ja estava publicada (id={version['id']}).")
    return version


def run_one(client: PortalApiClient, spec: dict, agent_id: str) -> dict:
    label = spec["entrypoint"]["type"]
    print(f"\n=== {label}: {spec['name']} ===")

    _ensure_runtime_published(client, spec)

    category = client.get_or_create_category(CATEGORY_NAME, CATEGORY_SLUG, "Automacoes de demonstracao real da Biason.")
    automation = client.get_or_create_automation(
        key=spec["key"],
        name=spec["name"],
        slug=spec["slug"],
        category_id=category["id"],
        description=f"Demonstracao real de {label} via Automation Agent.",
        timeout_seconds=120,
    )
    print(f"Automacao: {automation['name']} (id={automation['id']})")

    raw_manifest = build_raw_manifest(spec)
    versions = client.list_automation_versions(automation["id"])
    version = next((v for v in versions if v.get("version") == DEMO_VERSION), None)

    if version is None:
        version = client.create_automation_version(
            automation["id"], raw_manifest, idempotency_key=f"biason-demo-{automation['id']}-{DEMO_VERSION}"
        )
        print(f"Versao {DEMO_VERSION} criada (id={version['id']}).")
    else:
        print(f"Versao {DEMO_VERSION} ja existia (id={version['id']}, status={version['status']}).")

    if version.get("status") in {"blocked", "invalid"}:
        print(
            f"AVISO: a versao {DEMO_VERSION} (id={version['id']}) ja esta em status "
            f"'{version['status']}' de uma rodada anterior e e imutavel - suba DEMO_VERSION "
            f"neste script (ex.: '1.0.2') e rode de novo."
        )
        return {"entrypoint": label, "automation": spec["name"], "status": f"blocked_immutable_version:{version['id']}"}

    if version.get("status") != "published":
        built = build_package_zip(
            spec["package_source_dir"],
            f"{spec['key']}-{DEMO_VERSION}.zip",
            automation_yaml=raw_manifest,
            manifest_version=DEMO_VERSION,
        )
        print(f"Pacote construido: {built.file_name} ({built.size_bytes} bytes, sha256={built.sha256[:12]}...)")

        upload = client.initiate_package_upload(version["id"], built.file_name, built.size_bytes, built.sha256)
        with tempfile.TemporaryDirectory(prefix="biason_demo_") as tmp:
            tmp_path = os.path.join(tmp, built.file_name)
            with open(tmp_path, "wb") as handle:
                handle.write(built.zip_bytes)
            client.upload_package_bytes(upload["id"], tmp_path, built.file_name)
        client.complete_package_upload(upload["id"])
        print("Pacote enviado e confirmado.")

        version = client.publish_automation_version(version["id"])
        print(f"Versao publicada (status={version['status']}).")
    else:
        print("Versao ja estava publicada - reaproveitando.")

    print("Criando execucao real...")
    # Regressao: a Idempotency-Key era fixa por versao ("biason-demo-run-{id
    # da versao}"). Como a versao 1.0.1 e reaproveitada em toda rodada
    # (nao republicamos a cada vez), toda chamada a POST /executions com essa
    # chave batia no mesmo registro do backend (modules/shared/application/
    # idempotency.py: chave repetida = REPLAY, devolve a execucao ORIGINAL em
    # vez de criar uma nova) - por isso powershell/executable sempre voltavam
    # com o MESMO execution_id de rodadas anteriores (inclusive de antes do
    # Agent.Service ter sido reiniciado com o binario corrigido), e o
    # resultado observado era o destino final daquela execucao zumbi (lease
    # expirado / cancelamento forcado), nunca uma execucao nova de verdade
    # contra o Agent atual. Cada rodada do harness agora usa uma chave unica.
    execution = client.create_execution(
        version["id"],
        agent_id=agent_id,
        parameters=spec["parameters"],
        idempotency_key=f"biason-demo-run-{version['id']}-{uuid.uuid4().hex[:12]}",
    )
    execution_id = execution.get("execution_id") or execution.get("id") or execution.get("execution", {}).get("id")
    print(f"Execucao criada: {execution_id}. Aguardando conclusao (ate 120s)...")

    try:
        observed = wait_until_terminal(client, execution_id, timeout_seconds=120)
    except ExecutionTimeoutError as exc:
        print(f"TIMEOUT do harness aguardando a execucao: {exc}")
        return {"entrypoint": label, "automation": spec["name"], "status": "harness_timeout", "execution_id": execution_id}

    print(f"Status final: {observed.status}")
    if observed.result:
        print("Resultado retornado pela automacao:")
        print(json.dumps(observed.result, indent=2, ensure_ascii=False))
    if observed.error_output:
        print(f"Saida de erro: {observed.error_output}")
    if observed.artifacts:
        print("Artefatos gerados:")
        for a in observed.artifacts:
            print(f"  - {a.get('file_name') or a.get('name')} ({a.get('size_bytes', '?')} bytes)")

    return {
        "entrypoint": label,
        "automation": spec["name"],
        "status": observed.status,
        "execution_id": execution_id,
        "artifacts": len(observed.artifacts or []),
    }


def main() -> int:
    print(f"Conectando ao Portal em {PORTAL_API_URL} ...")
    client = PortalApiClient(PORTAL_API_URL)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print("Login OK.")

    agents = client.list_agents()
    online_agents = [a for a in agents if a.get("connectivity_status") == "online" or a.get("status") == "online"]
    if not online_agents:
        print("NENHUM agente online encontrado. Verifique se o Agent.Service esta rodando e conectado.")
        return 3
    agent = online_agents[0]
    agent_id = agent.get("id") or agent.get("agent_id")
    print(f"Agente alvo: {agent.get('name', agent_id)} (id={agent_id})")

    results = []
    for spec in RUNTIME_SPECS:
        package_dir = spec["package_source_dir"]
        if not os.path.isdir(package_dir):
            print(f"\n=== {spec['entrypoint']['type']}: {spec['name']} ===")
            print(f"PULADO: pacote nao encontrado em {package_dir} (ainda nao foi copiado para o certification-packages).")
            results.append({"entrypoint": spec["entrypoint"]["type"], "automation": spec["name"], "status": "skipped_no_package"})
            continue
        try:
            results.append(run_one(client, spec, agent_id))
        except PortalApiError as exc:
            print(f"ERRO de API ao rodar {spec['key']}: {exc}")
            results.append({"entrypoint": spec["entrypoint"]["type"], "automation": spec["name"], "status": f"api_error: {exc}"})
        except Exception as exc:  # noqa: BLE001 - queremos continuar pros outros runtimes mesmo se um falhar
            print(f"ERRO inesperado ao rodar {spec['key']}: {exc}")
            results.append({"entrypoint": spec["entrypoint"]["type"], "automation": spec["name"], "status": f"error: {exc}"})

    print("\n\n========================================")
    print("RESUMO - execucao real por tipo de entrypoint")
    print("========================================")
    all_ok = True
    for r in results:
        ok = r["status"] == "succeeded"
        all_ok = all_ok and ok
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {r['entrypoint']:<18} {r['automation']:<55} status={r['status']}")

    client.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
