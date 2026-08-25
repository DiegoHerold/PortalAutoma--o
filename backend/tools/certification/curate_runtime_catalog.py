"""
Biason - Curadoria do catalogo de Runtimes do Portal

O usuario pediu pra reduzir o catalogo de Runtimes (visivel em
Automacoes > Runtimes no Portal) so aos que o Agent de fato usa hoje, e
"apagar" o resto - o catalogo tinha crescido pra 9 entradas (varias de
experimentos anteriores: node-browser, powershell-standard,
python-background, standalone-executable, etc.) sem nenhuma automacao real
publicada usando a maioria delas.

Limitacao real, verificada direto nas rotas do backend
(modules/catalog/api/routes.py): NAO existe DELETE /runtimes nem DELETE
/runtime-versions - so publish/deprecate/block por RuntimeVersion. Ou seja,
a API do Portal deliberadamente nao permite apagar um runtime de vez
(mantem auditoria/historico). O mais proximo de "apagar" que a API
permite e DEPRECAR toda RuntimeVersion do runtime - ele some das opcoes
ativas pra publicar automacao nova, mas o registro continua existindo.

Mantidos (KEEP_RUNTIME_IDS) - os unicos que o Agent (RuntimeLauncher.cs)
realmente sabe executar, cobrindo os 3 usos que a Biason precisa:
  - python-core      -> automacao de aplicativo/processo em segundo plano
                         (entrypoint python_function/python_module - roda
                         sempre invisivel, e o "background" de verdade).
  - python-desktop    -> automacao de aplicativo VISIVEL/interativa
                         (entrypoint python_desktop, usa pyautogui/pywinauto
                         num desktop real - precisa de InteractivePoolSize>0
                         no Agent, ja corrigido nesta rodada).
  - powershell        -> scripts PowerShell, visivel ou invisivel
                         (entrypoint powershell_script - nao baixa nada do
                         Runtime Store, usa o powershell/pwsh ja instalado
                         na maquina; a janela agora segue execution.mode).
  - executable        -> qualquer executavel .NET/nativo empacotado
                         (entrypoint executable - mesma logica de
                         visibilidade do powershell).
  - python-browser    -> navegador real via Playwright, visivel ou invisivel
                         (entrypoint browser_playwright - precisa de
                         BrowserPoolSize>0, ja corrigido, e do bundle
                         Playwright+Chromium provisionado por
                         provision-runtimes.ps1).

Qualquer OUTRO runtime_id no catalogo (node-browser, powershell-standard,
python-background, standalone-executable, playwright-browser duplicado,
etc.) nao corresponde a nenhum caso de RuntimeLauncher.BuildStartInfo (ou
duplica um dos 5 acima com outro nome) - e deprecado.

Roda de dentro do container do backend:
  docker compose exec -T backend python -m tools.certification.curate_runtime_catalog
"""

from __future__ import annotations

import os
import sys

from tools.certification.api_client import PortalApiClient, PortalApiError

PORTAL_API_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")

# runtime_id (a "key" do runtime no Portal) que ficam ativos.
KEEP_RUNTIME_IDS = {
    "python-core",
    "python-desktop",
    "powershell",
    "executable",
    "python-browser",
}


def main() -> int:
    print(f"Conectando ao Portal em {PORTAL_API_URL} ...")
    client = PortalApiClient(PORTAL_API_URL)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print("Login OK.\n")

    runtimes = client.list_runtimes()
    print(f"{len(runtimes)} runtime(s) encontrados no catalogo:\n")

    kept = []
    deprecated = []
    already_inactive = []
    failures = []

    for runtime in runtimes:
        runtime_key = runtime.get("key") or runtime.get("id")
        versions = runtime.get("versions", [])
        keep = runtime_key in KEEP_RUNTIME_IDS

        status_word = "MANTER" if keep else "DEPRECAR"
        print(f"[{status_word}] {runtime_key} (id={runtime['id']}) - {len(versions)} versao(oes)")

        if keep:
            kept.append(runtime_key)
            continue

        for version in versions:
            v_status = version.get("status")
            v_label = f"{runtime_key}:{version.get('version')}"
            if v_status in {"deprecated", "blocked"}:
                print(f"    - {v_label}: ja estava '{v_status}', nada a fazer.")
                already_inactive.append(v_label)
                continue
            try:
                client.deprecate_runtime_version(version["id"])
                print(f"    - {v_label}: depreciado (estava '{v_status}').")
                deprecated.append(v_label)
            except PortalApiError as exc:
                print(f"    - {v_label}: FALHOU ao depreciar ({exc}).")
                failures.append(v_label)

    print("\n========================================")
    print("RESUMO DA CURADORIA")
    print("========================================")
    print(f"Mantidos ({len(kept)}): {', '.join(sorted(set(kept))) or '(nenhum)'}")
    print(f"Depreciados agora ({len(deprecated)}): {', '.join(deprecated) or '(nenhum)'}")
    print(f"Ja estavam inativos ({len(already_inactive)}): {', '.join(already_inactive) or '(nenhum)'}")
    if failures:
        print(f"FALHARAM ({len(failures)}): {', '.join(failures)}")
    print(
        "\nNota: o Portal nao tem endpoint de DELETE para runtimes - 'deprecar' e o mais "
        "perto de apagar que a API permite (o registro continua existindo pra auditoria, "
        "mas some das opcoes ativas pra publicar automacao nova)."
    )

    client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
