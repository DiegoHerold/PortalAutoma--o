"""
Biason - Demo de Automacao de Navegador (Playwright)

Automacao real de demonstracao: abre um Chromium de verdade via Playwright,
navega ate uma pagina local (evita depender de um site externo), extrai
informacoes da pagina, tira um screenshot como artefato e devolve um
resultado estruturado - o mesmo caminho que uma automacao real de conferencia
de portal/site de terceiros percorreria no Agent.

Visivel ou invisivel: controlado pelo parametro "headless" recebido no
contexto de execucao (o mesmo "parameters" que a automacao recebe do
Portal). Por padrao roda headless=True (invisivel, uso normal em produção
- servidor sem ninguem olhando a tela). Publique a execucao com
{"headless": false} para ver o Chromium abrindo de verdade na tela (exige
execution.mode="interactive" no manifesto, para o Agent nao esconder a
janela - veja RuntimeLauncher.CreateBase).
"""

import os


def run(context: dict) -> dict:
    from playwright.sync_api import sync_playwright

    workspace = os.environ.get("AUTOMATION_WORKSPACE", ".")
    artifacts_path = os.environ.get("AUTOMATION_ARTIFACTS_PATH", os.path.join(workspace, "artifacts"))

    headless = bool(context.get("headless", True))
    print(f"[Biason] Iniciando automacao de navegador (headless={headless})...")

    # Pagina local gerada na hora - evita depender de internet/site externo
    # para a demonstracao funcionar (e por isso a automacao NAO declara a
    # capacidade "internet_access": ela nunca sai da maquina).
    test_html_path = os.path.join(workspace, "temp", "biason_demo_page.html")
    os.makedirs(os.path.dirname(test_html_path), exist_ok=True)
    with open(test_html_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>Biason Assessoria Empresarial - Demo</title></head>
<body>
    <h1 id="title">Biason Assessoria Empresarial</h1>
    <p id="description">Pagina de teste para validacao real de automacao de navegador (Playwright).</p>
    <div id="data">
        <span class="item">Certidao Negativa Federal</span>
        <span class="item">Certidao Negativa Estadual</span>
        <span class="item">Certidao Negativa Municipal</span>
        <span class="item">Certidao FGTS</span>
    </div>
</body>
</html>""")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        browser_context = browser.new_context()
        page = browser_context.new_page()

        page.goto(f"file:///{test_html_path.replace(os.sep, '/')}")
        print("[Biason] Pagina carregada.")

        title = page.text_content("#title")
        description = page.text_content("#description")
        items = page.query_selector_all(".item")
        item_texts = [item.text_content() for item in items]

        print(f"[Biason] Titulo: {title}")
        print(f"[Biason] Itens encontrados: {len(item_texts)}")

        screenshot_path = os.path.join(artifacts_path, "biason_demo_screenshot.png")
        os.makedirs(artifacts_path, exist_ok=True)
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[Biason] Screenshot salvo em {screenshot_path}")

        browser_context.close()
        browser.close()
        print("[Biason] Navegador encerrado.")

    return {
        "headless": headless,
        "title": title,
        "description": description,
        "itens": item_texts,
        "screenshot": "biason_demo_screenshot.png",
    }
