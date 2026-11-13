import { mkdirSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Pendências (13/11/2026): o botão "Continuar processo" do e-mail abre o aviso no Portal (com
 * login: sem estar logado, entra e volta para o aviso); continuar uma vez; de novo, diz quem já
 * continuou; a página Pendências lista o que aguarda.
 */

const TELAS = "../docs/pendencias-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string };

async function preparar(page: Page, { logado = true, jaContinuado = false } = {}) {
  const erros: string[] = [];
  const pedidos: Pedido[] = [];
  page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  if (logado) {
    await page.addInitScript(() => {
      window.localStorage.setItem("portal_token", "token-de-teste");
      window.localStorage.setItem("portal_theme", "light");
    });
  }
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  let continuado = jaContinuado;
  const item = (chave: string, rotulo: string) => ({
    id: `pnd_${chave}`, item: chave, rotulo, motivo: "2 rubricas a parametrizar", desde: em(-3600),
    situacao: continuado ? "continuada" : "aguardando", resolvida_em: continuado ? em(-300) : null,
    resolvida_via: continuado ? "email" : null, resolvida_por: continuado ? "Ana Lima" : null,
    continuacao_execucao_id: continuado ? "exe_nova" : null });
  const situacao = () => {
    const itens = [item("5081", "Strass Matriz"), item("5066", "Planet")];
    return { execucao_id: "exe_1", automacao: { id: 7, nome: "Integração Contábil · Folha" }, avisado_em: em(-3500), itens,
      aguardando: continuado ? 0 : 2, pode_continuar: !continuado,
      resolucao: continuado ? { situacao: "continuada", resolvida_em: em(-300), resolvida_via: "email", resolvida_por: "Ana Lima",
        continuacao_execucao_id: "exe_nova" } : null };
  };
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const r: Request = route.request();
    const caminho = new URL(r.url()).pathname.replace("/api/v1", "");
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (r.method() !== "GET") pedidos.push({ metodo: r.method(), caminho });
    if (caminho === "/auth/login") return json({ access_token: "token-novo", token_type: "bearer" });
    if (caminho === "/auth/me") {
      const autorizacao = r.headers()["authorization"];
      if (!autorizacao) return json({ detail: "Not authenticated" }, 401);
      return json({ id: 1, email: "ti@biason.net", name: "TI Biason", role: "admin", permissions: [], rbac_permissions: [] });
    }
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/pendencias/avisos/pav_1") return json(situacao());
    if (caminho === "/pendencias/avisos/pav_1/continuar" || caminho === "/pendencias/execucoes/exe_1/continuar") {
      if (continuado) return json({ erro: "Este processo já foi continuado.", resolucao: situacao().resolucao }, 409);
      continuado = true;
      return json({ execucao_id: "exe_nova", itens: ["5081", "5066"] });
    }
    if (caminho === "/pendencias") return json({ execucoes: continuado ? [] : [{ execucao_id: "exe_1", automacao: { id: 7, nome: "Integração Contábil · Folha" },
      pode_continuar: true, desde: em(-3600), itens: situacao().itens }] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros, pedidos };
}

test("botão do e-mail: sem login entra e volta; continua uma vez", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page, { logado: false });
  await page.goto("/pendencias/pav_1");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("E-mail").fill("ti@teste.invalid");
  await page.getByLabel("Senha", { exact: true }).fill("senha-de-teste");
  await page.getByRole("button", { name: /Entrar no portal/ }).click();
  await expect(page).toHaveURL(/\/pendencias\/pav_1$/);  // voltou para a pendência
  await expect(page.getByRole("heading", { name: "Integração Contábil · Folha precisa de você" })).toBeVisible();
  const itens = page.getByTestId("itens-da-pendencia");
  await expect(itens.locator("[data-item='5081']")).toContainText("Strass Matriz");
  await expect(itens.locator("[data-item='5081']")).toContainText("2 rubricas a parametrizar");
  await page.screenshot({ path: `${TELAS}/aviso-1440.png`, fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Continuar processo" }).click();
  await expect(page.getByTestId("continuado")).toContainText("Processo continuado: 2 itens entraram na fila.");
  await expect(page.getByRole("link", { name: "Acompanhar" })).toHaveAttribute("href", "/execucoes/exe_nova");
  expect(pedidos.filter((p) => p.caminho.endsWith("/continuar"))).toHaveLength(1);
  expect(erros).toEqual([]);
});

test("botão do e-mail de novo: diz quem já continuou e não continua", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page, { jaContinuado: true });
  await page.goto("/pendencias/pav_1");
  const ja = page.getByTestId("ja-continuado");
  await expect(ja).toContainText("Este processo já foi continuado há 5 min por Ana Lima pelo botão do e-mail.");
  await expect(ja).toContainText("vale uma vez");
  await expect(page.getByRole("button", { name: "Continuar processo" })).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/ja-continuado-1440.png`, fullPage: true, animations: "disabled" });
  expect(pedidos).toEqual([]);
  expect(erros).toEqual([]);
});

test("página Pendências: lista o que aguarda e continua", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/pendencias");
  const grupo = page.getByTestId("lista-de-pendencias").locator("[data-execucao='exe_1']");
  await expect(grupo).toContainText("Integração Contábil · Folha");
  await expect(grupo).toContainText("2 itens aguardando");
  await page.screenshot({ path: `${TELAS}/pendencias-1440.png`, fullPage: true, animations: "disabled" });
  await grupo.getByRole("button", { name: "Continuar processo" }).click();
  await expect(page.getByTestId("continuado")).toBeVisible();
  await expect.poll(() => pedidos.some((p) => p.caminho === "/pendencias/execucoes/exe_1/continuar")).toBe(true);
  expect(erros).toEqual([]);
});
