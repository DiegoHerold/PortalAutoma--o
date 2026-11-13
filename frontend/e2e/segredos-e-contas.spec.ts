import { mkdirSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Segredos e contas de serviço (13/11/2026): a lista de segredos mostra quem usa e o último uso;
 * liga e desliga automações; a aba Técnico liga um segredo; a conta de serviço mostra a credencial
 * uma única vez e tem papel e times.
 */

const TELAS = "../docs/segredos-telas";
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
  const segredos = [
    { id: "sec_1", chave: "dominio.senha_banco", nome: "Senha do banco da Domínio", descricao: "Leitura da folha", situacao: "active",
      versao: 2, versao_criada_em: em(-86400), expira_em: null, vencido: false, atualizado_em: em(-86400), ultimo_uso: em(-3600),
      automacoes: [{ id: 7, nome: "Integração Contábil · Folha", ligado_em: em(-90000), ultimo_uso: em(-3600) }] },
    { id: "sec_2", chave: "smtp.senha", nome: "Senha do e-mail", descricao: null, situacao: "disabled", versao: 1,
      versao_criada_em: em(-900000), expira_em: null, vencido: false, atualizado_em: em(-900000), ultimo_uso: null, automacoes: [] },
  ];
  const conta = { id: "sa_1", nome: "ERP Protheus", descricao: "Lê o histórico", situacao: "active", vencida: false,
    papel: { id: 5, nome: "Integração ERP", slug: "integracao-erp" }, times: [{ id: 3, nome: "Folha" }], expira_em: null,
    ultimo_uso: em(-120), criada_em: em(-86400 * 3), credencial_final: "Xy9z", credencial_criada_em: em(-86400 * 3),
    tem_credencial: true, usuario_id: 40 };
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const r: Request = route.request();
    const url = new URL(r.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (r.method() !== "GET") pedidos.push({ metodo: r.method(), caminho, corpo: r.postData() ? JSON.parse(r.postData() as string) : null });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/segredos" && r.method() === "GET") return json({ segredos });
    if (caminho === "/segredos/sec_1/versoes") return json({ versoes: [
      { versao: 2, criada_em: em(-86400), criada_por: "1", expira_em: null, revogada_em: null, atual: true },
      { versao: 1, criada_em: em(-900000), criada_por: "1", expira_em: null, revogada_em: null, atual: false }] });
    if (caminho.startsWith("/segredos/") && r.method() !== "GET") return route.fulfill({ status: 204, body: "" });
    if (caminho === "/segredos/da-automacao/7") return json({ segredos: [
      { id: "sec_1", chave: "dominio.senha_banco", nome: "Senha do banco da Domínio", situacao: "active", vencido: false, ultimo_uso: em(-3600) }] });
    if (caminho === "/secrets" && r.method() === "POST") return json({ secret: { id: "sec_3", key: "erp.token" }, version: { id: "v", version: 1 } }, 201);
    if (caminho === "/automations") return json([{ id: 7, name: "Integração Contábil · Folha", status: "active" },
      { id: 9, name: "Conferência de guias", status: "active" }]);
    if (caminho === "/automations/7") return json({ id: 7, name: "Integração Contábil · Folha", slug: "ic", key: "dominio.ic", category_id: 1,
      executor_type: "python_script", default_priority: "normal", timeout_seconds: 3600, max_retries: 1, is_active: true, status: "active" });
    if (caminho === "/automations/7/formulario") return json({ origem: "portal", versao: 1, pode_editar: true, item: null, colunas: [], tipos: [], entrada: [] });
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, maquinas: [], aguardando: { fila: [], perdidos: [] },
      fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, execucoes: [] });
    if (caminho === "/historico") return json({ execucoes: [], cursor: null });
    if (caminho === "/instancias-diretas") return json({ instancias: [] });
    if (caminho === "/contas-de-servico" && r.method() === "GET") return json({ contas: [conta] });
    if (caminho === "/contas-de-servico" && r.method() === "POST") return json({ conta: { ...conta, id: "sa_2", nome: "Power BI" },
      credencial: "psa_CredencialDeTeste_0123456789abcdefghijklmnop" }, 201);
    if (caminho === "/contas-de-servico/sa_1/credencial") return json({ conta, credencial: "psa_OutraCredencial_9876543210zyxwvutsrqpon" });
    if (caminho === "/roles") return json([{ id: 1, name: "Administrador", slug: "admin" }, { id: 5, name: "Integração ERP", slug: "integracao-erp" }]);
    if (caminho === "/teams") return json([{ id: 3, name: "Folha", status: "active", organization_id: 1, key: "folha" },
      { id: 4, name: "Fiscal", status: "active", organization_id: 1, key: "fiscal" }]);
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros, pedidos };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("segredos: lista com quem usa e último uso; ligar automações; novo segredo com a chave", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/secrets");
  const banco = page.locator("[data-segredo='dominio.senha_banco']");
  await expect(banco).toContainText("Integração Contábil · Folha");
  await expect(banco).toContainText("há 1 h");
  await expect(banco).toContainText("Ativo");
  await expect(page.locator("[data-segredo='smtp.senha']")).toContainText("nenhuma automação");
  await expect(page.locator("[data-segredo='smtp.senha']")).toContainText("Desativado");
  await page.screenshot({ path: `${TELAS}/segredos-1920.png`, fullPage: true, animations: "disabled" });

  await banco.getByRole("button", { name: "Senha do banco da Domínio" }).click();
  const detalhes = page.getByTestId("detalhes-do-segredo");
  await expect(detalhes).toContainText('senha = a.segredo("dominio.senha_banco")');
  await expect(detalhes).toContainText("Versão 2");
  await detalhes.getByLabel("Conferência de guias").check();
  await detalhes.getByRole("button", { name: "Salvar automações" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/segredos/sec_1/automacoes")?.corpo).toEqual({ automacoes: [7, 9] });
  await page.screenshot({ path: `${TELAS}/segredo-detalhes-1920.png`, animations: "disabled" });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: /Novo segredo/ }).first().click();
  await page.getByLabel("Nome").fill("Token do ERP");
  await expect(page.getByLabel("Chave")).toHaveValue("token_do_erp");  // a chave vem do nome
  await page.getByLabel("Chave").fill("erp.token");
  await page.getByLabel("Valor", { exact: true }).fill("abc-123-xyz");
  await page.getByLabel("Confirmar valor").fill("abc-123-xyz");
  await page.getByRole("button", { name: "Criar segredo" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/secrets")?.corpo).toMatchObject({ key: "erp.token", name: "Token do ERP", value: "abc-123-xyz" });
  expect(erros).toEqual([]);
});

test("técnico: segredos que a automação usa, ligar e desligar", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/automations/7");
  await page.getByRole("button", { name: "Técnico" }).click();
  const bloco = page.getByTestId("tecnico-segredos");
  await expect(bloco).toContainText("dominio.senha_banco");
  await expect(bloco).toContainText("usado há 1 h");
  await bloco.getByLabel("Segredo para ligar").selectOption("sec_2");
  await bloco.getByRole("button", { name: "Ligar", exact: true }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "POST" && p.caminho === "/segredos/da-automacao/7/sec_2")).toBe(true);
  await bloco.getByRole("button", { name: "Desligar dominio.senha_banco" }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/segredos/da-automacao/7/sec_1")).toBe(true);
  await bloco.screenshot({ path: `${TELAS}/tecnico-segredos.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("contas de serviço: papel e times; credencial uma vez só; nova credencial", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/service-accounts");
  const erp = page.locator("[data-conta='ERP Protheus']");
  await expect(erp).toContainText("Integração ERP");
  await expect(erp).toContainText("Folha");
  await expect(erp).toContainText("psa_…Xy9z");
  await expect(erp).toContainText("Ativa");
  await page.screenshot({ path: `${TELAS}/contas-de-servico-1920.png`, fullPage: true, animations: "disabled" });

  await page.getByRole("button", { name: /Nova conta/ }).click();
  await page.getByLabel(/Nome \(o sistema/).fill("Power BI");
  await expect(page.getByLabel(/Papel/).locator("option")).toHaveText(["Escolha o papel...", "Integração ERP"]);  // admin não
  await page.getByLabel(/Papel/).selectOption("5");
  await page.getByLabel("Fiscal").check();
  await page.getByRole("button", { name: "Criar e mostrar a credencial" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/contas-de-servico")?.corpo).toMatchObject({ nome: "Power BI", papel_id: 5, times: [4] });
  const uma = page.getByTestId("credencial-uma-vez");
  await expect(uma.getByTestId("credencial")).toHaveText("psa_CredencialDeTeste_0123456789abcdefghijklmnop");
  await expect(uma).toContainText("Authorization: Bearer psa_CredencialDeTeste");
  await expect(page.getByRole("button", { name: "Fechar" })).toBeDisabled();  // só depois de guardar
  await page.screenshot({ path: `${TELAS}/credencial-uma-vez.png`, animations: "disabled" });
  await uma.getByLabel("Guardei a credencial num lugar seguro").check();
  await page.getByRole("button", { name: "Fechar" }).click();
  await expect(page.getByTestId("credencial-uma-vez")).toHaveCount(0);

  await erp.getByRole("button", { name: "Nova credencial para ERP Protheus" }).click();
  await expect(page.getByText("psa_…Xy9z para de funcionar na hora", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Gerar nova" }).click();
  await expect(page.getByTestId("credencial")).toHaveText("psa_OutraCredencial_9876543210zyxwvutsrqpon");
  expect(erros).toEqual([]);
});
