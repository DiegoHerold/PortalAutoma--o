import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Telas grandes (1920): a escala de texto revista (nem gigante, nem miúdo) e o "← Voltar" das
 * telas de dentro. A API é simulada só aqui.
 */

const TELAS = "../docs/tipografia-telas";
mkdirSync(TELAS, { recursive: true });

const AUTOMACAO = { id: 7, name: "Integração Contábil · Folha", slug: "ic", key: "dominio.integracao_contabil", category_id: 1, executor_type: "direto",
  default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true, status: "active", description: "Integração contábil da folha na Domínio." };

async function preparar(page: Page) {
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
    if (caminho === "/auth/me") return json({ id: 1, email: "admin@teste.invalid", name: "Admin de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, execucoes: [], fila: { esperando: 2, perdidos: 0, termina_em: em(3600), sem_previsao: 0 },
      maquinas: [{ id: "mch_194", nome: "MAQ194", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: false, rodando: null, proximo: null }] });
    if (caminho === "/painel/recentes") return json({ maquinas: [{ id: "mch_194", nome: "MAQ194" }], automacoes: [
      { automation_id: 7, automacao: AUTOMACAO.name, pode_executar: true, ultima: { execucao_id: "exe_9", status: "succeeded", quando: em(-1800), maquinas: ["MAQ194"], itens: ["5076", "5081"] } },
      { automation_id: 9, automacao: "Conferência de guias", pode_executar: true, ultima: { execucao_id: "exe_8", status: "failed", quando: em(-7200), maquinas: ["FISCAL-01"], itens: ["7310"] } }] });
    if (caminho === "/historico") return json({ cursor: null, execucoes: [
      { execucao_id: "exe_9", status: "succeeded", automation_id: 7, automacao: AUTOMACAO.name, itens: ["5081", "5076"], total_itens: 2, maquinas: "MAQ194", iniciada_em: em(-9000), concluida_em: em(-7400), duracao_s: 1600, previsto_s: 1500, falha: null },
      { execucao_id: "exe_8", status: "failed", automation_id: 7, automacao: AUTOMACAO.name, itens: ["5066"], total_itens: 1, maquinas: "MAQ194", iniciada_em: em(-12000), concluida_em: em(-11000), duracao_s: 1000, previsto_s: 600, falha: "Rubricas: o Total não bateu" }] });
    if (caminho === "/fila") return json({ gerado_em: em(0), perdidos: [], maquinas: [], jobs: [] });
    if (caminho === "/automations") return json([AUTOMACAO, { ...AUTOMACAO, id: 9, name: "Conferência de guias", description: "Confere as guias do mês." }]);
    if (caminho === "/automations/7") return json(AUTOMACAO);
    if (caminho === "/automations/7/formulario") return json({ origem: "portal", versao: 1, pode_editar: true, item: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo" },
      entrada: [{ chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true, padrao: null, opcoes: [], ajuda: "Mês e ano da folha (MM/AAAA).", afeta_trabalho: false, origem: "automacao", fora_de_uso: false }],
      colunas: [], tipos: [{ tipo: "texto", rotulo: "Texto" }, { tipo: "mes_ano", rotulo: "Mês/ano" }] });
    if (caminho === "/automations/7/itens") return json({ definicao: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo", afetam_trabalho: [] }, pode_editar: true,
      contagem: { ativos: 2, total: 2 }, proximo: null, itens: [
        { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: {}, ativo: true },
        { chave: "5076", rotulo: "Filial de teste", grupo: "5081", atributos: {}, ativo: true }] });
    if (caminho === "/automations/7/itens/proposta") return json(null);
    if (caminho === "/categories") return json([{ id: 1, name: "Folha", slug: "folha" }]);
    if (caminho.startsWith("/execucoes/")) return route.fulfill({ status: 404, contentType: "application/json",
      body: JSON.stringify({ error: { code: "NOT_FOUND", message: "Execução não encontrada." } }) });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.evaluate(() => document.fonts.ready);
}

for (const [nome, rota, pronto] of [
  ["painel", "/dashboard", "ultimas-automacoes"],
  ["historico", "/historico", null],
  ["catalogo", "/automations", null],
  ["automacao", "/automations/7", "o-que-pede"],
  ["automacao-itens", "/automations/7#itens", "itens"],
] as const) {
  test(`1920: ${nome}`, async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    const { erros } = await preparar(page);
    await abrir(page, rota);
    if (pronto) await expect(page.getByTestId(pronto)).toBeVisible();
    else await expect(page.locator("main h1")).toBeVisible();
    // Nenhum texto de conteúdo menor que 13px nem título maior que 40px em 1920.
    const tamanhos = await page.evaluate(() => {
      const visiveis = [...document.querySelectorAll("main *")].filter((el) => {
        const r = (el as HTMLElement).getBoundingClientRect();
        return r.width > 0 && r.height > 0 && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim());
      });
      return visiveis.map((el) => parseFloat(getComputedStyle(el).fontSize));
    });
    expect(Math.min(...tamanhos)).toBeGreaterThanOrEqual(13);
    expect(Math.max(...tamanhos)).toBeLessThanOrEqual(40);
    await page.screenshot({ path: `${TELAS}/${nome}-1920.png`, animations: "disabled" });
    expect(erros).toEqual([]);
  });
}

test("voltar: de dentro de uma automação volta para onde estava", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations/7");  // aberta direto (primeira tela da aba): volta para o Catálogo
  await expect(page.getByTestId("botao-voltar")).toBeVisible();
  await page.getByTestId("botao-voltar").click();
  await expect(page).toHaveURL(/\/automations$/);
  await expect(page.getByTestId("botao-voltar")).toHaveCount(0);
  await page.getByRole("link", { name: `Abrir ${AUTOMACAO.name}` }).click();  // navegando pelo Portal: volta para a anterior
  await expect(page).toHaveURL(/\/automations\/7/);
  await page.getByRole("button", { name: "Itens" }).click();
  await page.getByTestId("botao-voltar").click();
  await expect(page).toHaveURL(/\/automations$/);
  await page.getByRole("link", { name: "Histórico" }).first().click();
  await expect(page.getByTestId("botao-voltar")).toHaveCount(0);  // página do menu: sem voltar
  expect(erros).toEqual([]);
});

test("voltar: execução aberta direto vai para o Histórico", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await preparar(page);
  await page.goto("/execucoes/exe_9");
  await expect(page.getByText("Execução não encontrada.").first()).toBeVisible();
  await page.getByTestId("botao-voltar").click();
  await expect(page).toHaveURL(/\/historico$/);
});
