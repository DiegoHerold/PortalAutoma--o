"""
Demonstracao real: cria a automacao "Biason - Demo Processamento Fiscal" no
catalogo do Portal (via API HTTP real, os mesmos endpoints que o frontend
usa), publica a versao, e dispara uma execucao real no Agent conectado -
depois espera o resultado e mostra o que aconteceu.

Roda de dentro do container do backend:
  docker compose exec -T backend python -m tools.certification.demo_seed
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import yaml

from tools.certification.api_client import PortalApiClient, PortalApiError
from tools.certification.packaging import build_package_zip
from tools.certification.execution import wait_until_terminal, ExecutionTimeoutError

PORTAL_API_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")
PACKAGE_SOURCE_DIR = "/certification-packages/demo_fiscal"

CATEGORY_NAME = "Biason Demo"
CATEGORY_SLUG = "biason-demo"

AUTOMATION_KEY = "demo.biason_fiscal"
AUTOMATION_NAME = "Biason - Demo Processamento Fiscal"
AUTOMATION_SLUG = "biason-demo-processamento-fiscal"
AUTOMATION_VERSION = "1.0.0"

RUNTIME_ID = "python-core"
RUNTIME_VERSION = "3.13"


def build_raw_manifest() -> str:
    document = {
        "schema_version": 1,
        "id": AUTOMATION_KEY,
        "name": AUTOMATION_NAME,
        "version": AUTOMATION_VERSION,
        "description": "Demonstracao real: processa documentos fiscais, reporta progresso, gera relatorio.",
        "category": CATEGORY_SLUG,
        "runtime": {"id": RUNTIME_ID, "version": RUNTIME_VERSION},
        "entrypoint": {
            "type": "python-function",
            "module": "automation.main",
            "function": "run",
            "path": "automation/main.py",
        },
        "execution": {
            "mode": "background",
            "timeout_seconds": 120,
            "graceful_cancellation_seconds": 10,
        },
        "resources": {"cpu_units": 1, "memory_mb": 256, "disk_mb": 100},
        "capabilities": {"required": ["windows", "agent.background_execution"]},
    }
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def main() -> int:
    print(f"Conectando ao Portal em {PORTAL_API_URL} ...")
    client = PortalApiClient(PORTAL_API_URL)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print("Login OK.")

    category = client.get_or_create_category(
        CATEGORY_NAME, CATEGORY_SLUG, "Automacoes de demonstracao real da Biason."
    )
    print(f"Categoria: {category['name']} (id={category['id']})")

    automation = client.get_or_create_automation(
        key=AUTOMATION_KEY,
        name=AUTOMATION_NAME,
        slug=AUTOMATION_SLUG,
        category_id=category["id"],
        description="Demonstracao real de processamento fiscal via Automation Agent.",
        timeout_seconds=120,
    )
    print(f"Automacao: {automation['name']} (id={automation['id']})")

    raw_manifest = build_raw_manifest()
    versions = client.list_automation_versions(automation["id"])
    version = next((v for v in versions if v.get("version") == AUTOMATION_VERSION), None)

    if version is None:
        version = client.create_automation_version(
            automation["id"], raw_manifest, idempotency_key=f"biason-demo-{automation['id']}-{AUTOMATION_VERSION}"
        )
        print(f"Versao {AUTOMATION_VERSION} criada (id={version['id']}).")
    else:
        print(f"Versao {AUTOMATION_VERSION} ja existia (id={version['id']}, status={version['status']}).")

    if version.get("status") != "published":
        built = build_package_zip(
            PACKAGE_SOURCE_DIR,
            f"{AUTOMATION_KEY}-{AUTOMATION_VERSION}.zip",
            automation_yaml=raw_manifest,
            manifest_version=AUTOMATION_VERSION,
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

    agents = client.list_agents()
    online_agents = [a for a in agents if a.get("connectivity_status") == "online" or a.get("status") == "online"]
    if not online_agents:
        print("NENHUM agente online encontrado. Verifique se o Agent.Service esta rodando e conectado.")
        return 3
    agent = online_agents[0]
    agent_id = agent.get("id") or agent.get("agent_id")
    print(f"Agente alvo: {agent.get('name', agent_id)} (id={agent_id})")

    print("Criando execucao real...")
    execution = client.create_execution(
        version["id"],
        agent_id=agent_id,
        parameters={
            "documentos": [
                "nota_fiscal_1234.xml",
                "guia_das_agosto_2026.pdf",
                "folha_pagamento_agosto.pdf",
                "certidao_negativa_receita.pdf",
                "contrato_cliente_042.pdf",
            ]
        },
        idempotency_key=f"biason-demo-run-{version['id']}",
    )
    execution_id = execution.get("execution_id") or execution.get("id") or execution.get("execution", {}).get("id")
    print(f"Execucao criada: {execution_id}")
    print("Aguardando conclusao (ate 120s)...")

    try:
        observed = wait_until_terminal(client, execution_id, timeout_seconds=120)
    except ExecutionTimeoutError as exc:
        print(f"TIMEOUT do harness aguardando a execucao: {exc}")
        return 3

    print()
    print("========================================")
    print(f"Status final: {observed.status}")
    print("========================================")
    if observed.result:
        print("Resultado retornado pela automacao:")
        print(json.dumps(observed.result, indent=2, ensure_ascii=False))
    if observed.error_output:
        print(f"Saida de erro: {observed.error_output}")
    if observed.artifacts:
        print("\nArtefatos gerados:")
        for a in observed.artifacts:
            print(f"  - {a.get('file_name') or a.get('name')} ({a.get('size_bytes', '?')} bytes)")

    client.close()
    return 0 if observed.status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
