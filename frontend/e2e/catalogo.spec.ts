import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Catálogo (12/11/2026): cartões com o que importa para usar (categoria, rodando/fila, última
 * execução, Executar); a página da automação sem o Executar repetido; a aba Técnico em blocos.
 */

const TELAS = "../docs/catalogo-telas";
mkdirSync(TELAS, { recursive: true });

const FORMULARIO = {
  origem: "portal", versao: 1, pode_editar: true, item: null, colunas: [], tipos: [],
  entrada: [{ chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true, padrao: null, opcoes: [], ajuda: null,
              afeta_trabalho: false, origem: "automacao", fora_de_uso: false }],
};

async function preparar(page: Page, eu: Record<string, unknown> = { role: "admin", rbac_permissions: [] }) {
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", "light");
  });
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const url = new URL(route.request().url());
    const caminho = url.pathname.replace("/api/v1", "");
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", permissions: [], ...eu });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    const base = { slug: "x", executor_type: "python_script", default_priority: "normal", timeout_seconds: 3600, max_retries: 1, is_active: true,
                   status: "active", package_url: null };
    const automacoes = [
      { ...base, id: 7, name: "Integração Contábil · Folha", category_id: 1, description: "Integração contábil da folha na Domínio.", key: "dominio.ic" },
      { ...base, id: 9, name: "Conferência de guias", category_id: 2, description: "Confere as guias do mês." },
      { ...base, id: 11, name: "Relatório de férias", category_id: 1, description: null },
    ];
    if (caminho === "/automations") return json(automacoes);
    if (caminho === "/automations/7") return json(automacoes[0]);
    if (caminho === "/categories") return json([{ id: 1, name: "Folha", slug: "folha" }, { id: 2, name: "Fiscal", slug: "fiscal" }]);
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, maquinas: [], aguardando: { fila: [], perdidos: [] },
      fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 },
      execucoes: [{ execucao_id: "exe_r", automation_id: 9, automacao: "Conferência de guias" }].slice(0, 0) });
    if (caminho === "/painel/recentes") return json({ maquinas: [], automacoes: [
      { automation_id: 7, ultima: { execucao_id: "exe_1", status: "succeeded", quando: em(-7200) } },
      { automation_id: 9, ultima: { execucao_id: "exe_2", status: "failed", quando: em(-600) } }] });
    if (caminho === "/painel/executaveis") return json({ automacoes: [{ id: 7, nome: "Integração Contábil · Folha" }, { id: 11, nome: "Relatório de férias" }] });
    if (caminho === "/fila") return json({ gerado_em: em(0), jobs: [{ job_id: "j1", automation_id: 11 }, { job_id: "j2", automation_id: 11 }], perdidos: [], maquinas: [] });
    if (caminho === "/automations/7/formulario") return json(FORMULARIO);
    if (caminho === "/historico") return json({ execucoes: [], cursor: null });
    if (caminho === "/automations/7/sources") return json([{ id: 1, type: "github", owner: "biason", repository: "integracao", branch: "main",
      automation_path: ".", sync_status: "up_to_date" }]);
    if (caminho === "/automations/7/versions") return json([]);
    if (caminho === "/schedules") return json([{ id: 3, automation_id: 7, is_active: true, timezone: "America/Sao_Paulo", schedule_type: "monthly",
      day_of_month: 5, time_of_day: "08:00", cron_expression: null }]);
    if (caminho === "/triggers") return json([]);
    if (caminho === "/instancias-diretas") return json({ instancias: [
      { id: "dri_1", status: "aprovada", automation_id: 7, automacao: "Integração Contábil · Folha", nome_informado: "MAQ10", versao: "0.1.0",
        maquina_id: "mch_10", maquina_nome: "MAQ10", inscrita_em: em(-86400), ultimo_sinal: em(-30) }] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("catálogo: cartões com categoria, fila, última execução e Executar", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations");
  const folha = page.locator("[data-automacao='7']");
  await expect(folha).toContainText("Folha");
  await expect(folha.getByTestId("ultima-execucao")).toContainText("Última há 2 h");
  await expect(folha.getByTestId("ultima-execucao")).toContainText("Concluída");
  await expect(page.locator("[data-automacao='9']").getByTestId("ultima-execucao")).toContainText("Falhou");
  await expect(page.locator("[data-automacao='11']")).toContainText("2 na fila");
  await expect(page.locator("[data-automacao='11']").getByTestId("ultima-execucao")).toHaveText("Ainda não rodou");
  // Só quem pode executar vê o botão; os detalhes técnicos saíram do cartão.
  await expect(page.locator("[data-automacao='9']").getByRole("button", { name: "Executar" })).toHaveCount(0);
  await expect(folha).not.toContainText("Timeout");
  await page.screenshot({ path: `${TELAS}/catalogo-1920.png`, fullPage: true, animations: "disabled" });
  await folha.getByRole("button", { name: "Executar" }).click();
  await expect(page.getByTestId("executar")).toBeVisible();  // a mesma janela do Painel
  await expect(page).toHaveURL(/\/automations$/);
  expect(erros).toEqual([]);
});

test("catálogo: quem não gerencia automações não vê criar, editar nem arquivar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { role: "operator", rbac_permissions: ["automacoes.ver", "painel.ver"] });
  await abrir(page, "/automations");
  await expect(page.locator("[data-automacao]")).toHaveCount(3);
  await expect(page.getByRole("button", { name: /Nova automação/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Editar / })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Arquivar / })).toHaveCount(0);
  expect(erros).toEqual([]);
});

test("automação: um Executar só, e a aba Técnico em blocos", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations/7");
  await expect(page.getByText("Nada rodando desta automação agora.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Executar" })).toHaveCount(1);  // só o do cabeçalho

  await page.getByRole("button", { name: "Técnico" }).click();
  const tecnico = page.getByTestId("tecnico");
  await expect(tecnico.getByTestId("tecnico-versoes")).toContainText("GitHub biason/integracao @ main");
  await expect(tecnico.getByTestId("tecnico-como-roda")).toContainText("MAQ10");
  await expect(tecnico.getByTestId("tecnico-como-roda")).toContainText("Aprovada");
  await expect(tecnico.getByTestId("tecnico-disparos")).toContainText("Ligado");
  await expect(tecnico.getByTestId("tecnico-acessos").getByRole("link", { name: /Exceções de acesso/ })).toHaveAttribute("href", "/automations/7/acessos");
  await expect(tecnico).not.toContainText(/worker/i);  // saiu o que não se usa mais
  await expect(tecnico.getByTestId("tecnico-dev")).not.toHaveAttribute("open", "");
  await page.screenshot({ path: `${TELAS}/automacao-tecnico-1920.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});
