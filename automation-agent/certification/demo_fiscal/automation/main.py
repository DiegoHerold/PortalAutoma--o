"""
Biason - Demo de Processamento Fiscal

Automacao real de demonstracao: recebe uma lista de documentos, "processa"
cada um (com um pequeno delay para simular trabalho real), reporta
progresso a cada item, escreve um relatorio como artefato e retorna um
resultado estruturado - exatamente o mesmo caminho que uma automacao real
de producao percorreria no Agent.
"""

import os
import time
from datetime import datetime, timezone


def run(context: dict) -> dict:
    workspace = os.environ.get("AUTOMATION_WORKSPACE", ".")
    artifacts_path = os.environ.get("AUTOMATION_ARTIFACTS_PATH", os.path.join(workspace, "artifacts"))
    output_path = os.environ.get("AUTOMATION_OUTPUT_PATH", os.path.join(workspace, "output"))

    documentos = context.get("documentos", [
        "nota_fiscal_1234.xml",
        "guia_das_agosto_2026.pdf",
        "folha_pagamento_agosto.pdf",
        "certidao_negativa_receita.pdf",
        "contrato_cliente_042.pdf",
    ])
    total = len(documentos)

    print(f"[Biason] Iniciando processamento de {total} documento(s) fiscal(is)...")
    processados = []

    for i, doc in enumerate(documentos, 1):
        print(f"[Biason] Processando {i}/{total}: {doc}")
        time.sleep(1)  # simula trabalho real (leitura, validacao, etc.)
        processados.append({
            "documento": doc,
            "status": "processado",
            "processado_em": datetime.now(timezone.utc).isoformat(),
        })
        pct = 100 * i // total
        print(f"[Biason] Progresso: {i}/{total} ({pct}%)")

    report_path = os.path.join(artifacts_path, "relatorio_processamento_fiscal.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Biason Assessoria Empresarial\n")
        f.write("Relatorio de Processamento Fiscal (demo)\n")
        f.write("=========================================\n\n")
        f.write(f"Executado em: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Total de documentos: {total}\n\n")
        for p in processados:
            f.write(f"  - {p['documento']}: {p['status']} ({p['processado_em']})\n")

    print(f"[Biason] Relatorio gravado em {report_path}")
    print("[Biason] Processamento concluido com sucesso.")

    return {
        "processados": len(processados),
        "total": total,
        "documentos": processados,
    }
