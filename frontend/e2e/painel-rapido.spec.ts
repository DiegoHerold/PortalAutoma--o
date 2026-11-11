import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Painel prático: o botão "Executar automação" (busca e já abre a janela Executar) e as últimas
 * automações, com filtro por máquina e "Repetir" com os mesmos itens. API simulada só aqui.
 */

const TELAS = "../docs/painel-rapido-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

const FORMULARIO = {
  origem: "portal", versao: 1, pode_editar: true, item: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo" },
  entrada: [{ chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true, padrao: null, opcoes: [], ajuda: null,
    afeta_trabalho: false, origem: "automacao", fora_de_uso: false }],
  colunas: [], tipos: [{ tipo: "texto", rotulo: "Texto" }],
};

async function preparar(page: Page, tema: "light" | "dark" = "light") {
  const pedidos: Pedido[] = [];
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(([t]) => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", t);
  }, [tema]);
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  const recentes = [
    { automation_id: 7, automacao: "Integração Contábil · Folha", pode_executar: true,
      ultima: { execucao_id: "exe_9", status: "succeeded", quando: em(-1800), maquinas: ["MAQ194"], itens: ["5076", "5081"] } },
    { automation_id: 9, automacao: "Conferência de guias", pode_executar: true,
      ultima: { execucao_id: "exe_8", status: "failed", quando: em(-7200), maquinas: ["FISCAL-01"], itens: ["7310"] } },
    { automation_id: 11, automacao: "Relatório de férias", pode_executar: false,
      ultima: { execucao_id: "exe_7", status: "running", quando: em(-300), maquinas: ["MAQ194"], itens: [] } },
  ];
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "operator", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, execucoes: [], fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 },
      maquinas: [{ id: "mch_194", nome: "MAQ194", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: false, rodando: null, proximo: null },
                 { id: "mch_f1", nome: "FISCAL-01", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: false, rodando: null, proximo: null }] });
    if (caminho === "/painel/recentes") {
      const maquina = url.searchParams.get("maquina");
      const nome = maquina === "mch_f1" ? "FISCAL-01" : maquina === "mch_194" ? "MAQ194" : null;
      return json({ automacoes: recentes.filter((r) => !nome || r.ultima.maquinas.includes(nome)),
        maquinas: [{ id: "mch_f1", nome: "FISCAL-01" }, { id: "mch_194", nome: "MAQ194" }] });
    }
    if (caminho === "/painel/executaveis") return json({ automacoes: [
      { id: 9, nome: "Conferência de guias", descricao: "Confere as guias do mês." },
      { id: 7, nome: "Integração Contábil · Folha", descricao: "Integração contábil da folha na Domínio." }] });
    if (/^\/automations\/\d+\/formulario$/.test(caminho)) return json(FORMULARIO);
    if (/^\/automations\/\d+\/itens$/.test(caminho)) return json({ definicao: null, pode_editar: false, contagem: { ativos: 3, total: 3 }, proximo: null,
      itens: [{ chave: "5076", rotulo: "Filial de teste", grupo: "5081", atributos: {}, ativo: true },
              { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: {}, ativo: true },
              { chave: "7310", rotulo: "Empresa fiscal de teste", grupo: null, atributos: {}, ativo: true }] });
    if (/^\/automations\/\d+\/itens\/pedir-execucao$/.test(caminho)) return json({ execution_id: "exe_x", jobs: [{ job_id: "j", existente: false }], itens: [] }, 201);
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

for (const tema of ["light", "dark"] as const) {
  test(`painel: últimas automações e o botão de disparo — ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    const { erros } = await preparar(page, tema);
    await abrir(page, "/dashboard");
    const ultimas = page.getByTestId("ultimas-automacoes");
    await expect(ultimas.locator("[data-automacao]")).toHaveCount(3);
    await expect(ultimas.locator("[data-automacao='11']").getByText("Você só acompanha esta automação.")).toBeVisible();
    await expect(ultimas.locator("[data-automacao='9']").getByText("Falhou")).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `${TELAS}/painel-${tema === "light" ? "claro" : "escuro"}.png`, animations: "disabled" });
    expect(erros).toEqual([]);
  });
}

test("executar automação: achar pelo nome e pedir, sem entrar na automação", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/dashboard");
  await page.getByRole("button", { name: "Executar automação" }).click();
  const busca = page.getByTestId("busca-executar");
  await busca.getByLabel("Buscar automação para executar").fill("folha");
  await expect(busca.getByRole("option")).toHaveCount(1);
  await page.screenshot({ path: `${TELAS}/busca.png`, animations: "disabled" });
  await page.keyboard.press("Enter");
  const janela = page.getByTestId("executar");
  await janela.getByLabel("Escolher Empresa fiscal de teste").check();
  await janela.getByLabel("Competência").fill("10/2026");
  await page.getByRole("button", { name: /Executar 1 empresa/ }).click();
  await expect(janela).toHaveCount(0);
  expect(pedidos.filter((p) => p.caminho === "/automations/7/itens/pedir-execucao").map((p) => p.corpo)).toEqual([
    { chaves: ["7310"], com_filiais: true, parametros: { competencia: "10/2026" } }]);
  // depois do pedido, o Painel relê
  await expect.poll(() => pedidos.filter((p) => p.caminho.startsWith("/painel/recentes")).length).toBeGreaterThan(1);
  expect(erros).toEqual([]);
});

test("atalho E abre a busca; setas e Enter escolhem", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { erros } = await preparar(page);
  await abrir(page, "/dashboard");
  await expect(page.getByTestId("ultimas-automacoes").locator("[data-automacao]")).toHaveCount(3);
  await page.keyboard.press("e");
  await expect(page.getByLabel("Buscar automação para executar")).toBeFocused();
  await page.keyboard.press("ArrowDown");  // pode chegar antes da lista: a marca não sai dela
  await expect(page.getByTestId("busca-executar").getByRole("option")).toHaveCount(2);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");  // já no fim: fica no último
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("executar")).toBeVisible();
  await expect(page.getByText("Executar Integração Contábil · Folha")).toBeVisible();
  expect(erros).toEqual([]);
});

test("repetir: abre com os mesmos itens marcados; o filtro por máquina fica guardado", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const ultimas = page.getByTestId("ultimas-automacoes");
  await ultimas.getByLabel("Filtrar por máquina").selectOption("mch_f1");
  await expect(ultimas.locator("[data-automacao]")).toHaveCount(1);
  expect(pedidos.some((p) => p.caminho === "/painel/recentes?limite=3&maquina=mch_f1")).toBe(true);
  await page.reload();
  await expect(page.getByTestId("ultimas-automacoes").getByLabel("Filtrar por máquina")).toHaveValue("mch_f1");
  await ultimas.getByLabel("Filtrar por máquina").selectOption("");
  await ultimas.locator("[data-automacao='7']").getByRole("button", { name: "Repetir" }).click();
  const janela = page.getByTestId("executar");
  await expect(janela.getByLabel("Escolher Matriz de teste")).toBeChecked();
  await expect(janela.getByLabel("Escolher Empresa fiscal de teste")).not.toBeChecked();
  await page.screenshot({ path: `${TELAS}/repetir.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("resposta fora do formato nas últimas automações não derruba o Painel", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page);
  await page.route(`${API_DE_TESTE}/painel/recentes**`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route(`${API_DE_TESTE}/painel/executaveis**`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
  await abrir(page, "/dashboard");
  await expect(page.getByRole("heading", { name: "Agora" })).toBeVisible();
  await expect(page.getByTestId("nada-rodando")).toBeVisible();
  await page.getByRole("button", { name: "Executar automação" }).click();
  await expect(page.getByText("Você ainda não pode executar nenhuma automação.")).toBeVisible();
  expect(erros).toEqual([]);
});
