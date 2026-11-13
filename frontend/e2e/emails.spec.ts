import { mkdirSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * E-mails (13/11/2026): o que o Portal enviou, o que falhou ou foi recusado, o que a automação mandou
 * pela máquina; detalhe com a mensagem; reenviar; domínios permitidos; e-mail de teste.
 */

const TELAS = "../docs/emails-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

async function preparar(page: Page) {
  const erros: string[] = [];
  const pedidos: Pedido[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    try {  // também roda no iframe da mensagem, que é isolado (sem localStorage): ali não faz nada
      window.localStorage.setItem("portal_token", "token-de-teste");
      window.localStorage.setItem("portal_theme", "light");
    } catch { /* iframe isolado */ }
  });
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  const base = { cc: [], cco: [], tentativas: 1, proxima_tentativa_em: null, anexos: [], execucao_id: null, motivo: null, meio: "graph" };
  const ic = { id: 7, nome: "Integração Contábil · Folha" };
  const emails = [
    { ...base, id: "eml_1", origem: "automacao", tipo: "aviso", automacao: ic, execucao_id: "exe_1", para: ["jeverton@biason.net"],
      cc: ["gestor@biason.net"], assunto: "Folha 10/2026: rubricas a parametrizar", situacao: "enviado", criado_em: em(-600),
      enviado_em: em(-600), anexos: [{ nome: "rubricas.csv", tamanho: 120 }] },
    { ...base, id: "eml_2", origem: "automacao", tipo: "aviso", automacao: ic, para: ["joao@cliente.com.br"], assunto: "Folha 10/2026: integração concluída",
      situacao: "recusado", motivo: "domínio não permitido: cliente.com.br", tentativas: 0, criado_em: em(-1200), enviado_em: null },
    { ...base, id: "eml_3", origem: "portal", tipo: "notificacao", automacao: null, para: ["ti@biason.net"], assunto: "MAQ10 sem sinal",
      situacao: "falhou", motivo: "Microsoft Graph recusou o envio (HTTP 400)", criado_em: em(-3600), enviado_em: null },
    { ...base, id: "eml_4", origem: "maquina", tipo: "mensagem", automacao: ic, meio: "outlook", para: ["samara@biason.net"],
      assunto: "Folha 09/2026 (Outlook)", situacao: "enviado_pela_maquina", criado_em: em(-86400 * 2), enviado_em: em(-86400 * 2) },
  ];
  const dominios = ["biason.net", "strass.com.br"];
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const r: Request = route.request();
    const url = new URL(r.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (r.method() !== "GET") pedidos.push({ metodo: r.method(), caminho, corpo: r.postData() ? JSON.parse(r.postData() as string) : null });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@biason.net", name: "TI Biason", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/emails") {
      const situacao = url.searchParams.get("situacao");
      return json({ emails: situacao ? emails.filter((e) => e.situacao === situacao) : emails,
        resumo_24h: { enviado: 1, recusado: 1, falhou: 1 }, cursor: null });
    }
    if (caminho === "/emails/configuracao") return json({ situacao: "ligado", remetente: "portal@biason.net", dominio_do_remetente: "biason.net", dominios });
    if (caminho === "/emails/eml_3") return json({ email: { ...emails[2], html: null, texto: "MAQ10 está sem sinal há 5 min." } });
    if (caminho === "/emails/eml_1") return json({ email: { ...emails[0], html: "<h1>Rubricas a parametrizar</h1><p>8781 · Ajuda de custo</p>", texto: null } });
    if (caminho === "/emails/eml_3/reenviar") return json({ id: "eml_3", situacao: "enviado", motivo: null });
    if (caminho === "/emails/teste") return json({ id: "eml_9", situacao: "enviado", motivo: null });
    if (caminho === "/emails/dominios" && r.method() === "POST") return json({ dominio: "cliente.com.br" }, 201);
    if (caminho.startsWith("/emails/dominios/")) return route.fulfill({ status: 204, body: "" });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros, pedidos };
}

test("e-mails: lista com origem e situação, filtro, detalhe e reenviar", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/emails");
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await expect(page.getByTestId("estado-do-envio")).toContainText("Envio ligado (Microsoft Graph)");
  await expect(page.getByTestId("estado-do-envio")).toContainText("portal@biason.net");
  const lista = page.getByTestId("lista-de-emails");
  await expect(lista.locator("[data-email='Folha 10/2026: rubricas a parametrizar']")).toContainText("para jeverton@biason.net, gestor@biason.net · Integração Contábil · Folha");
  await expect(lista.locator("[data-email='Folha 10/2026: integração concluída']")).toContainText("domínio não permitido: cliente.com.br");
  await expect(lista.locator("[data-email='Folha 09/2026 (Outlook)']")).toContainText("pela máquina (outlook)");
  await expect(lista.locator("[data-email='MAQ10 sem sinal']")).toContainText("Portal · notificação");
  await page.screenshot({ path: `${TELAS}/emails-1920.png`, fullPage: true, animations: "disabled" });

  await page.getByRole("button", { name: "Falharam" }).click();
  await expect(lista.locator("li")).toHaveCount(1);
  await lista.getByRole("button", { name: /MAQ10 sem sinal/ }).click();
  const detalhe = page.getByTestId("detalhe-do-email");
  await expect(detalhe).toContainText("HTTP 400");
  await expect(detalhe).toContainText("MAQ10 está sem sinal há 5 min.");
  await detalhe.getByRole("button", { name: "Reenviar" }).click();
  await expect.poll(() => pedidos.some((p) => p.caminho === "/emails/eml_3/reenviar")).toBe(true);
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Todos" }).click();
  await lista.getByRole("button", { name: /rubricas a parametrizar/ }).click();
  await expect(page.getByTestId("detalhe-do-email")).toContainText("rubricas.csv");
  await expect(page.getByTestId("mensagem-html")).toHaveAttribute("sandbox", "");
  await expect(page.frameLocator("[data-testid='mensagem-html']").getByRole("heading", { name: "Rubricas a parametrizar" })).toBeVisible();
  await page.screenshot({ path: `${TELAS}/email-detalhe-1920.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("e-mails: domínios permitidos e e-mail de teste", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/emails");
  await page.getByRole("button", { name: "Mandar um teste para mim" }).click();
  await expect.poll(() => pedidos.some((p) => p.caminho === "/emails/teste")).toBe(true);
  await page.getByRole("button", { name: /Domínios permitidos/ }).click();
  const dominios = page.getByTestId("dominios-permitidos");
  await expect(dominios).toContainText("domínio do remetente: sempre permitido");
  await expect(dominios.locator("[data-dominio='strass.com.br']")).toBeVisible();
  await dominios.getByLabel("Novo domínio").fill("cliente.com.br");
  await dominios.getByRole("button", { name: "Permitir" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/emails/dominios")?.corpo).toEqual({ dominio: "cliente.com.br" });
  await dominios.getByRole("button", { name: "Tirar strass.com.br" }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/emails/dominios/strass.com.br")).toBe(true);
  expect(erros).toEqual([]);
});
