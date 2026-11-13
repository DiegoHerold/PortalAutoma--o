import { mkdirSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Webhooks (13/11/2026): a lista mostra o que aciona, chamadas das últimas 24 h, último uso, proteção
 * e situação; o detalhe ensina a chamar (URL, cabeçalhos, o que pode mandar pelo formulário da
 * automação, exemplo) e mostra as chamadas; o token aparece uma vez; o migrado pede token novo.
 */

const TELAS = "../docs/webhooks-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

async function preparar(page: Page) {
  const erros: string[] = [];
  const pedidos: Pedido[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", "light");
  });
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  const erp = { id: "whk_1a2b3c4d5e6f7a8b", url: "https://portal.biason.net/api/v1/webhooks/whk_1a2b3c4d5e6f7a8b",
    automacao: { id: 7, nome: "Integração Contábil · Folha" }, nome: "ERP Protheus", descricao: "Fecha a folha no fim do mês",
    ativo: true, tem_token: true, token_final: "Q9xZ", token_criado_em: em(-86400 * 5), ips_permitidos: ["10.0.8.15/32"],
    limite_por_minuto: 30, ultimo_uso_em: em(-600), criado_em: em(-86400 * 5), migrado: false, chamadas_24h: { aceitas: 4, recusadas: 1 } };
  const antigo = { ...erp, id: "whk_9f8e7d6c5b4a3921", url: "https://portal.biason.net/api/v1/webhooks/whk_9f8e7d6c5b4a3921",
    nome: "Power Automate (antigo)", descricao: "Migrado do webhook antigo /folha. Gere um token novo e ligue.", ativo: false,
    tem_token: false, token_final: null, token_criado_em: null, ips_permitidos: [], ultimo_uso_em: null, migrado: true,
    chamadas_24h: { aceitas: 0, recusadas: 0 } };
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const r: Request = route.request();
    const url = new URL(r.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (r.method() !== "GET") pedidos.push({ metodo: r.method(), caminho, corpo: r.postData() ? JSON.parse(r.postData() as string) : null });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/webhooks" && r.method() === "GET") {
      return json({ webhooks: url.searchParams.get("automacao") === "7" ? [erp, antigo] : [erp, antigo] });
    }
    if (caminho === "/webhooks" && r.method() === "POST") return json({ webhook: { ...erp, id: "whk_novo", nome: "Power BI" },
      token: "wht_TokenDeTeste_0123456789abcdefghijklmnopq" }, 201);
    if (caminho === `/webhooks/${erp.id}/chamadas`) return json({ chamadas: [
      { id: "c1", recebida_em: em(-600), situacao: "aceita", motivo: null, codigo_http: 202, ip: "10.0.8.15", execucao_id: "exe_1", itens: 2 },
      { id: "c2", recebida_em: em(-900), situacao: "repetida", motivo: "Idempotency-Key repetida", codigo_http: 200, ip: "10.0.8.15", execucao_id: "exe_1", itens: 2 },
      { id: "c3", recebida_em: em(-1800), situacao: "recusada", motivo: "origem não permitida para este webhook", codigo_http: 403, ip: "200.1.2.3", execucao_id: null, itens: null }] });
    if (caminho.endsWith("/chamadas")) return json({ chamadas: [] });
    if (caminho === `/webhooks/${antigo.id}/token`) return json({ webhook: { ...antigo, tem_token: true, token_final: "AbCd" },
      token: "wht_OutroToken_9876543210zyxwvutsrqponmlkji" });
    if (caminho.startsWith("/webhooks/") && r.method() === "PUT") return json({ webhook: erp });
    if (caminho === "/automations/7/formulario") return json({ origem: "portal", versao: 1, pode_editar: true,
      item: { nome: "Empresa", chave: "codigo", grupo: null }, colunas: [], tipos: [],
      entrada: [{ chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true, padrao: null, opcoes: [], ajuda: null,
                  afeta_trabalho: false }] });
    if (caminho === "/automations") return json([{ id: 7, name: "Integração Contábil · Folha", status: "active", is_active: true },
      { id: 9, name: "Conferência de guias", status: "active", is_active: true }]);
    if (caminho === "/automations/7") return json({ id: 7, name: "Integração Contábil · Folha", slug: "ic", key: "dominio.ic", category_id: 1,
      executor_type: "python_script", default_priority: "normal", timeout_seconds: 3600, max_retries: 1, is_active: true, status: "active" });
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, maquinas: [], aguardando: { fila: [], perdidos: [] },
      fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, execucoes: [] });
    if (caminho === "/historico") return json({ execucoes: [], cursor: null });
    if (caminho === "/instancias-diretas") return json({ instancias: [] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros, pedidos };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("webhooks: cartões e resumo; detalhe em abas (chamadas, como chamar, proteção)", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/webhooks");
  const resumo = page.getByTestId("resumo-dos-webhooks");
  await expect(resumo).toContainText("Ligados1de 2");
  await expect(resumo).toContainText("1 sem token");
  await expect(resumo).toContainText("Aceitas nas últimas 24 h4");
  await expect(resumo).toContainText("Recusadas nas últimas 24 h1");
  const erp = page.locator("[data-webhook='ERP Protheus']");
  await expect(erp).toContainText("Integração Contábil · Folha");
  await expect(erp).toContainText("4aceitas 24 h");
  await expect(erp).toContainText("1recusadas 24 h");
  await expect(erp).toContainText("há 10 min");
  await expect(erp).toContainText("1 IP/rede");
  await expect(erp).toContainText("30/min");
  await expect(erp).toContainText("…Q9xZ");
  await expect(erp).toContainText("Ligado");
  await expect(page.locator("[data-webhook='Power Automate (antigo)']")).toContainText("Veio do webhook antigo: gere um token e ligue.");
  await page.screenshot({ path: `${TELAS}/webhooks-1920.png`, fullPage: true, animations: "disabled" });

  await erp.getByRole("button", { name: "ERP Protheus" }).click();
  const detalhes = page.getByTestId("detalhes-do-webhook");
  const chamadas = detalhes.getByTestId("chamadas-do-webhook");  // com chamadas, abre nelas
  await expect(chamadas.locator("[data-situacao='aceita']")).toContainText("ver execução (2 itens)");
  await expect(chamadas.locator("[data-situacao='recusada']")).toContainText("origem não permitida");
  await detalhes.getByRole("button", { name: /Só recusadas/ }).click();
  await expect(chamadas.locator("li")).toHaveCount(1);
  await page.screenshot({ path: `${TELAS}/webhook-chamadas-1920.png`, animations: "disabled" });

  await detalhes.getByRole("button", { name: "Como chamar" }).click();
  await expect(detalhes.getByTestId("url-do-webhook")).toHaveText("https://portal.biason.net/api/v1/webhooks/whk_1a2b3c4d5e6f7a8b");
  await expect(detalhes).toContainText("wht_…Q9xZ");
  await expect(detalhes.getByTestId("campos-do-webhook")).toContainText("parametros.competencia");
  await expect(detalhes.getByTestId("campos-do-webhook")).toContainText("chaves de empresa");
  await expect(detalhes.getByTestId("exemplo-do-webhook")).toContainText('"competencia": "10/2026"');
  await expect(detalhes.getByTestId("exemplo-do-webhook")).toContainText("Authorization: Bearer wht_…");
  await page.screenshot({ path: `${TELAS}/webhook-como-chamar-1920.png`, animations: "disabled" });

  await detalhes.getByRole("button", { name: "Proteção" }).click();
  await detalhes.getByLabel("IPs permitidos").fill("10.0.8.15\n10.0.9.0/24");
  await page.screenshot({ path: `${TELAS}/webhook-protecao-1920.png`, animations: "disabled" });
  await detalhes.getByRole("button", { name: "Salvar proteção" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/webhooks/whk_1a2b3c4d5e6f7a8b" && p.metodo === "PUT")?.corpo)
    .toEqual({ ips_permitidos: "10.0.8.15\n10.0.9.0/24", limite_por_minuto: 30 });
  expect(erros).toEqual([]);
});

test("webhooks: novo com token uma vez só; migrado gera token", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/webhooks");
  await page.getByRole("button", { name: /Novo webhook/ }).click();
  await page.getByLabel("Automação que ele aciona").selectOption("9");
  await page.getByLabel("Nome (quem vai chamar)").fill("Power BI");
  await page.getByLabel(/IPs permitidos/).fill("10.0.8.20");
  await page.getByRole("button", { name: "Criar e mostrar o token" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/webhooks" && p.metodo === "POST")?.corpo).toMatchObject({
    automation_id: 9, nome: "Power BI", ips_permitidos: "10.0.8.20", limite_por_minuto: 30 });
  const uma = page.getByTestId("token-uma-vez");
  await expect(uma.getByTestId("token")).toHaveText("wht_TokenDeTeste_0123456789abcdefghijklmnopq");
  await expect(page.getByRole("button", { name: "Fechar" })).toBeDisabled();
  await page.screenshot({ path: `${TELAS}/token-uma-vez.png`, animations: "disabled" });
  await uma.getByLabel("Guardei o token num lugar seguro").check();
  await page.getByRole("button", { name: "Fechar" }).click();
  await expect(page.getByTestId("token-uma-vez")).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.locator("[data-webhook='Power Automate (antigo)']").getByRole("button", { name: "Power Automate (antigo)" }).click();
  const detalhes = page.getByTestId("detalhes-do-webhook");
  await expect(detalhes).toContainText("Veio do webhook antigo");
  await expect(detalhes.getByTestId("url-do-webhook")).toBeVisible();  // sem token, abre em "Como chamar"
  await expect(detalhes.getByRole("button", { name: "Ligar" })).toHaveCount(0);  // sem token não liga
  await detalhes.getByRole("button", { name: "Gerar token" }).click();
  await page.getByRole("button", { name: "Gerar", exact: true }).click();
  await expect(page.getByTestId("token")).toHaveText("wht_OutroToken_9876543210zyxwvutsrqponmlkji");
  expect(erros).toEqual([]);
});

test("técnico: disparos mostram os webhooks da automação", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations/7");
  await page.getByRole("button", { name: "Técnico" }).click();
  const disparos = page.getByTestId("tecnico-disparos");
  await expect(disparos.locator("[data-webhook='ERP Protheus']")).toContainText("Ligado");
  await expect(disparos.locator("[data-webhook='Power Automate (antigo)']")).toContainText("Sem token");
  await expect(disparos).not.toContainText("em cadeia");
  expect(erros).toEqual([]);
});
