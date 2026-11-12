import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Fase 5: Painel (monitores e Central de telas), Máquinas com linha do tempo, Histórico e
 * Itens. A API é simulada só aqui; as telas são imagens sintéticas (e2e/fixtures).
 */

const TELAS = process.env.PLAYWRIGHT_SCREENSHOT_DIR ?? "../docs/fase-5-telas";
const IMAGENS: Record<string, Buffer> = {
  img_a: readFileSync(path.join(__dirname, "fixtures", "tela-a.jpg")),
  img_b: readFileSync(path.join(__dirname, "fixtures", "tela-b.jpg")),
};

function em(agora: number, s: number) {
  return new Date(agora + s * 1000).toISOString();
}

function execucao(agora: number, n: number, maquina: string, automacao: string, imagem: string, central = true) {
  return {
    execucao_id: `exe_${n}`, job_id: `job_${n}`, automation_id: 7, automacao, maquina_id: `mch_${n}`, maquina,
    modo: "direct", itens: [{ chave: String(5000 + n * 11), rotulo: `Empresa ${5000 + n * 11}` }], tentativa: 1,
    desde: em(agora, -600 - n * 120), decorrido_s: 600 + n * 120, falta_s: n === 3 ? null : 900 + n * 300,
    motivo_sem_previsao: n === 3 ? "aguardando_job_sem_previsao" : null,
    termino_previsto: n === 3 ? null : em(agora, 900 + n * 300),
    etapa: { etapa: n === 2 ? "trocar_empresa" : "rubricas", item: String(5000 + n * 11) },
    item: { item: String(5000 + n * 11), rotulo: `Empresa ${5000 + n * 11}` },
    progresso: { atual: 6 + n * 7, total: 50, rotulo: `centro ${6 + n * 7} de 50` }, pausa: null, atencoes: n === 1 ? 1 : 0,
    pode_ver_tela: central,
    tela: central ? { imagem_id: imagem, rotulo: "Salvou o centro", segundos_nesta_tela: 12 + n * 9, espera_rotulo: null, imagem: { situacao: "pronta", motivo: null } } : null,
    log: central ? [1, 2, 3, 4, 5, 6].map((i) => ({ id: `l${n}${i}`, nivel: i === 5 ? "aviso" : "info", texto: `Centro ${i + n * 7} de 50 conferido`, item: null, espera: false, quando: em(agora, -60 + i * 5) })) : null,
  };
}

function painel(agora: number, central = true) {
  return {
    gerado_em: new Date(agora).toISOString(), central,
    execucoes: [
      execucao(agora, 1, "FOLHA-01", "Integração Contábil · Folha", "img_b", central),
      execucao(agora, 2, "FOLHA-02", "Integração Contábil · Folha", "img_a", central),
      execucao(agora, 3, "FISCAL-01", "Conferência de guias", "img_b", central),
    ],
    maquinas: [
      { id: "mch_1", nome: "FOLHA-01", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: true, rodando: "Integração Contábil · Folha", proximo: null },
      { id: "mch_2", nome: "FOLHA-02", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: true, rodando: "Integração Contábil · Folha", proximo: null },
      { id: "mch_3", nome: "FISCAL-01", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: true, rodando: "Conferência de guias", proximo: null },
      { id: "mch_4", nome: "MAQ194", online: true, sessao_bloqueada: false, job_perdido: false, ocupada: false, rodando: null, proximo: { automacao: "Integração Contábil · Folha", inicio_previsto: em(agora, 1500) } },
    ],
    fila: { esperando: 5, perdidos: 0, termina_em: em(agora, 7200), sem_previsao: 0 },
  };
}

function linhaDoTempo(agora: number, antes = 6, depois = 6) {
  const inicio = agora - antes * 3600_000;
  const fim = agora + depois * 3600_000;
  const pos = (t: number) => ((t - inicio) / (fim - inicio)) * 100;
  const bloco = (tipo: string, a: number, b: number | null, automacao: string, conhecido = true) => ({
    tipo, inicio: new Date(a).toISOString(), fim: b ? new Date(b).toISOString() : null, fim_conhecido: conhecido,
    esquerda: pos(a), largura: pos(b ?? agora) - pos(a), cortado_no_inicio: false, cortado_no_fim: false,
    execucao_id: tipo === "previsto" ? null : "exe_1", job_id: "j", automacao, itens: ["5081"], situacao: null,
  });
  const marcas = [];
  for (let t = Math.ceil(inicio / 3600_000) * 3600_000; t <= fim; t += 3600_000) {
    marcas.push({ quando: new Date(t).toISOString(), posicao: pos(t) });
  }
  return {
    inicio: new Date(inicio).toISOString(), fim: new Date(fim).toISOString(), agora: new Date(agora).toISOString(), agora_posicao: pos(agora), marcas,
    maquinas: [
      { maquina_id: "mch_1", nome: "FOLHA-01", blocos: [bloco("feito", agora - 5 * 3600_000, agora - 3.6 * 3600_000, "Integração Contábil · Folha"),
        bloco("feito", agora - 3.4 * 3600_000, agora - 1.2 * 3600_000, "Integração Contábil · Folha"),
        bloco("rodando", agora - 0.4 * 3600_000, agora + 0.6 * 3600_000, "Integração Contábil · Folha"),
        bloco("previsto", agora + 0.7 * 3600_000, agora + 2.1 * 3600_000, "Integração Contábil · Folha")] },
      { maquina_id: "mch_2", nome: "FOLHA-02", blocos: [bloco("feito", agora - 2 * 3600_000, agora - 0.8 * 3600_000, "Conferência de guias"),
        bloco("rodando", agora - 0.3 * 3600_000, null, "Integração Contábil · Folha", false)] },
      { maquina_id: "mch_4", nome: "MAQ194", blocos: [bloco("previsto", agora + 0.4 * 3600_000, agora + 1.5 * 3600_000, "Integração Contábil · Folha")] },
    ],
  };
}

async function preparar(page: Page, tema: "light" | "dark" = "light", central = true) {
  const pedidos: Array<{ metodo: string; caminho: string; corpo: unknown }> = [];
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(([t]) => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", t);
  }, [tema]);
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    pedidos.push({ metodo: req.method(), caminho, corpo: req.postData() && req.headers()["content-type"]?.includes("json") ? JSON.parse(req.postData()!) : null });
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(b) });
    const agora = Date.now();
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/painel") return json(painel(agora, central));
    if (caminho === "/painel/linha-do-tempo") {
      return json(linhaDoTempo(agora, Number(url.searchParams.get("horas_antes") ?? 6), Number(url.searchParams.get("horas_depois") ?? 6)));
    }
    const img = caminho.match(/\/imagens\/(\w+)$/);
    if (img) return route.fulfill({ status: 200, contentType: "image/jpeg", body: IMAGENS[img[1]] ?? IMAGENS.img_a });
    if (caminho === "/instancias-diretas") return json({ instancias: [
      { id: "dri_1", status: "pendente", automation_id: 7, automacao: "Integração Contábil · Folha", nome_informado: "MAQ194", versao: "0.1.0", maquina_id: null, maquina_nome: null, inscrita_em: em(agora, -300), ultimo_sinal: em(agora, -20) },
      { id: "dri_2", status: "aprovada", automation_id: 9, automacao: "Conferência de guias", nome_informado: "FISCAL-01", versao: "0.1.0", maquina_id: "mch_3", maquina_nome: "FISCAL-01", inscrita_em: em(agora, -9000), ultimo_sinal: em(agora, -5) },
    ] });
    if (caminho === "/maquinas") return json({ maquinas: [{ id: "mch_4", nome: "MAQ194" }, { id: "mch_1", nome: "FOLHA-01" }] });
    if (caminho === "/historico") return json({ cursor: null, execucoes: [
      { execucao_id: "exe_9", status: "succeeded", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5081", "5076", "5075"], total_itens: 3, maquinas: "FOLHA-01", iniciada_em: em(agora, -9000), concluida_em: em(agora, -7400), duracao_s: 1600, previsto_s: 1500, falha: null },
      { execucao_id: "exe_8", status: "failed", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5066"], total_itens: 1, maquinas: "FOLHA-02", iniciada_em: em(agora, -12000), concluida_em: em(agora, -11000), duracao_s: 1000, previsto_s: 600, falha: "Rubricas: o Total não bateu" },
      { execucao_id: "exe_7", status: "succeeded", automation_id: 9, automacao: "Conferência de guias", itens: ["7310"], total_itens: 1, maquinas: "FISCAL-01", iniciada_em: em(agora, -20000), concluida_em: em(agora, -19400), duracao_s: 600, previsto_s: null, falha: null },
    ] });
    if (caminho === "/automations") return json([{ id: 7, name: "Integração Contábil · Folha", slug: "ic", category_id: 1 }]);
    if (caminho === "/automations/7/itens" && req.method() === "GET") return json({
      definicao: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo", afetam_trabalho: ["separar_por_custo"],
        atributos: { properties: { separar_por_custo: { type: "boolean", title: "Separar por custo" }, email: { type: "string", title: "E-mail" }, caminho_saida: { type: "string", title: "Pasta de destino" } } } },
      pode_editar: true, contagem: { ativos: 4, total: 4 }, proximo: null,
      itens: [
        { chave: "5066", rotulo: "Empresa sozinha de teste", grupo: null, atributos: { separar_por_custo: false }, ativo: true },
        { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: { separar_por_custo: true }, ativo: true },
        { chave: "5075", rotulo: "Filial A de teste", grupo: "5081", atributos: { separar_por_custo: false }, ativo: true },
        { chave: "5076", rotulo: "Filial B de teste", grupo: "5081", atributos: { separar_por_custo: true }, ativo: true },
      ] });
    if (caminho === "/automations/7/formulario") return json({ origem: "manifesto", versao: 0, pode_editar: true,
      item: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo" }, entrada: [], tipos: [],
      colunas: [{ chave: "separar_por_custo", rotulo: "Separar por custo", tipo: "sim_nao", obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: true },
        { chave: "email", rotulo: "E-mail", tipo: "email", obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false },
        { chave: "caminho_saida", rotulo: "Pasta de destino", tipo: "pasta", obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false }] });
    if (caminho === "/automations/7/itens/importar/previa") return json({
      novos: [{ chave: "6001", rotulo: "Nova de teste", grupo: null, atributos: {}, ativo: true }],
      alterados: [{ chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: {}, ativo: true, mudancas: ["atributos.email"] }],
      iguais: 16, erros: [] });
    if (caminho === "/automations/7/itens/pedir-execucao") return json({ execution_id: "exe_x", jobs: [{ job_id: "j", existente: false }] });
    if (caminho === "/fila") return json({ gerado_em: new Date(agora).toISOString(), jobs: [], perdidos: [], maquinas: [] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    if (caminho === "/notificacoes/preferencias") return json({ tipos: [], fila_minutos: 30, email: null, disponiveis: [], fila_minutos_limites: [5, 1440], envio_por_email: "desligado" });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

for (const tema of ["light", "dark"] as const) {
  for (const tela of [
    { nome: "1920", viewport: { width: 1920, height: 1080 } },
    { nome: "celular", viewport: { width: 390, height: 844 } },
  ]) {
    test(`painel com monitores — ${tela.nome}, ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
      await page.setViewportSize(tela.viewport);
      const { erros, pedidos } = await preparar(page, tema);
      await abrir(page, "/dashboard");
      await expect(page.getByTestId("monitor")).toHaveCount(3);
      await expect(page.getByText(/\d+ s nesta tela/).first()).toBeVisible();
      await expect(page.locator("img[alt='Salvou o centro']").first()).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: `${TELAS}/painel-${tela.nome}-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
      expect(pedidos.some((p) => p.caminho === "/painel/avisos")).toBe(true);
      expect(erros).toEqual([]);
    });
  }
}

test("texto cresce com a tela na escala legível", async ({ page }) => {
  await preparar(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await abrir(page, "/dashboard");
  const pequeno = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  await page.setViewportSize({ width: 1920, height: 1080 });
  const grande = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  expect(pequeno).toBeGreaterThanOrEqual(15);
  expect(pequeno).toBeLessThan(15.5);
  expect(grande).toBeGreaterThan(16.5);
  expect(grande).toBeLessThan(17.5);
});

test("central de telas em grade de 4 com o log ao lado", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/dashboard");
  await page.getByRole("tab", { name: "Central de telas" }).click();
  await page.getByRole("button", { name: "4", exact: true }).click();
  await expect(page.getByTestId("quadro")).toHaveCount(4);
  await expect(page.getByText("Próximo: Integração Contábil · Folha")).toBeVisible();
  await expect(page.getByText("Centro 13 de 50 conferido").first()).toBeVisible();
  await page.screenshot({ path: `${TELAS}/central-de-telas-1920.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("sem permissão de telas o monitor mostra só o andamento", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page, "light", false);
  await abrir(page, "/dashboard");
  await expect(page.getByTestId("monitor")).toHaveCount(3);
  await expect(page.getByRole("tab", { name: "Central de telas" })).toHaveCount(0);
  expect(pedidos.filter((p) => p.caminho.includes("/imagens/"))).toEqual([]);
  await page.screenshot({ path: `${TELAS}/painel-sem-telas-1440.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("máquinas: linha do tempo e automações diretas", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/maquinas");
  await expect(page.getByTestId("linha-do-tempo")).toBeVisible();
  await expect(page.getByText("Aguardando aprovação")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/maquinas-1920.png`, fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Gerenciar" }).click();
  await expect(page.getByText("Conectar uma automação direta")).toBeVisible();

  // 24 h: rola na horizontal em vez de espremer, sem horários encavalados, com o "agora" à vista
  await page.getByRole("button", { name: "Gerenciar" }).click();
  await page.getByRole("button", { name: "24 h" }).click();
  const rolagem = page.getByTestId("linha-do-tempo-rolagem");
  await expect.poll(() => rolagem.evaluate((n) => n.scrollWidth > n.clientWidth)).toBe(true);
  const sobrepostos = await rolagem.evaluate((n) => {
    const caixas = [...n.querySelectorAll(".tabular")].map((e) => e.getBoundingClientRect()).sort((a, b) => a.left - b.left);
    return caixas.some((c, i) => i > 0 && c.left < caixas[i - 1].right);
  });
  expect(sobrepostos).toBe(false);
  await expect.poll(() => rolagem.evaluate((n) => {
    const agora = n.querySelector("[data-agora]")!.getBoundingClientRect();
    const caixa = n.getBoundingClientRect();
    return agora.left > caixa.left + 160 && agora.right < caixa.right;
  })).toBe(true);
  await page.getByTestId("linha-do-tempo").screenshot({ path: `${TELAS}/maquinas-24h-1920.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("histórico: filtros escondidos até pedir", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/historico");
  await expect(page.getByTestId("historico").getByRole("listitem")).toHaveCount(3);
  await expect(page.getByLabel("Situação")).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/historico-1920.png`, fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: /Filtros/ }).click();
  await expect(page.getByLabel("Situação")).toBeVisible();
  expect(erros).toEqual([]);
});

test("itens: escolher, pedir execução e importar com prévia", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros, pedidos } = await preparar(page);
  await abrir(page, "/automations/7/itens");
  await expect(page.getByTestId("itens").getByRole("listitem")).toHaveCount(4);
  await page.getByLabel("Escolher Matriz de teste").check();
  await expect(page.getByText("1 escolhido(s)")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/itens-1920.png`, fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Executar", exact: true }).click();
  await page.getByRole("button", { name: /Executar 3 empresa/ }).click();  // a matriz e as duas filiais
  await expect.poll(() => pedidos.filter((p) => p.caminho.endsWith("/pedir-execucao")).map((p) => p.corpo))
    .toEqual([{ chaves: ["5081"], com_filiais: true, parametros: {} }]);
  await abrir(page, "/automations/7/itens");
  await page.getByRole("button", { name: "Importar" }).click();
  await page.locator("input[type=file]").setInputFiles({ name: "empresas.db", mimeType: "application/octet-stream", buffer: Buffer.from("SQLite format 3\0") });
  await expect(page.getByRole("button", { name: "Gravar 2" })).toBeEnabled();
  await page.screenshot({ path: `${TELAS}/itens-importar-previa.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("menu lateral: padrão sem rolagem, administração nas Configurações e itens escolhidos lá", async ({ page }) => {
  // notebook de 1366x768 com as barras do navegador: sobra ~650px de altura
  await page.setViewportSize({ width: 1366, height: 650 });
  const { erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const menu = page.locator("aside nav");
  await expect(menu.getByRole("link", { name: "Agents" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Auditoria" })).toHaveCount(0);
  await expect(page.getByText("BY BIASON", { exact: false })).toHaveCount(0);
  const tamanhoMenu = await menu.evaluate((n) => ({ conteudo: n.scrollHeight, visivel: n.clientHeight }));
  expect(tamanhoMenu.conteudo).toBeLessThanOrEqual(tamanhoMenu.visivel);
  await page.screenshot({ path: `${TELAS}/menu-padrao-1366.png`, animations: "disabled" });

  await abrir(page, "/settings");
  await expect(page.getByRole("heading", { name: "Menu e atalhos" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "Auditoria" })).toBeVisible();
  await page.getByLabel("Mostrar Auditoria no menu").check();
  await expect(menu.getByRole("link", { name: "Auditoria" })).toBeVisible();
  await page.getByLabel("Mostrar Fluxos no menu").uncheck();
  await expect(menu.getByRole("link", { name: "Fluxos" })).toHaveCount(0);
  await page.setViewportSize({ width: 1366, height: 980 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${TELAS}/configuracoes-1366.png`, animations: "disabled" });
  await page.setViewportSize({ width: 1366, height: 650 });

  await abrir(page, "/dashboard");
  await expect(menu.getByRole("link", { name: "Auditoria" })).toBeVisible();
  await abrir(page, "/settings");
  await page.getByRole("button", { name: "Restaurar padrão" }).click();
  await expect(menu.getByRole("link", { name: "Auditoria" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "Fluxos" })).toBeVisible();

  // recolhido: só os ícones (do mesmo tamanho) e ainda sem rolagem
  await page.getByRole("button", { name: "Recolher navegação" }).click();
  const icone = await menu.getByRole("link", { name: "Painel" }).locator("svg").boundingBox();
  expect(icone!.width).toBeGreaterThanOrEqual(22);
  const tamanhoRecolhido = await menu.evaluate((n) => ({ conteudo: n.scrollHeight, visivel: n.clientHeight }));
  expect(tamanhoRecolhido.conteudo).toBeLessThanOrEqual(tamanhoRecolhido.visivel);
  await page.locator("aside").screenshot({ path: `${TELAS}/menu-recolhido-1366.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("menu lateral: lista única sem títulos; arrastar para qualquer lugar fica gravado", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  const { erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const menu = page.locator("aside nav");
  const ordemDe = () => menu.locator("[data-item-menu]").evaluateAll((els) => els.map((e) => e.getAttribute("data-item-menu")));
  await expect(page.locator("aside").getByText("Portal de Automações")).toHaveCount(0);
  await expect(page.locator("aside img[alt='Biason']")).toBeVisible();
  // sem títulos de categoria (pedido de 12/11/2026)
  await expect(menu.locator("[data-grupo]")).toHaveCount(0);
  for (const titulo of ["Monitorar", "Catálogo", "Operação", "Infraestrutura"]) {
    await expect(menu.getByText(titulo, { exact: true })).toHaveCount(0);
  }

  await menu.locator("[data-item-menu='/historico']").dragTo(menu.locator("[data-item-menu='/dashboard']"));
  expect((await ordemDe()).slice(0, 4)).toEqual(["/historico", "/dashboard", "/fila", "/maquinas"]);
  // qualquer item vai para qualquer lugar (não há mais categorias)
  await menu.locator("[data-item-menu='/workers']").dragTo(menu.locator("[data-item-menu='/fila']"));
  expect((await ordemDe()).slice(0, 4)).toEqual(["/historico", "/dashboard", "/workers", "/fila"]);

  // pelo teclado: Alt+↓ no item focado
  await menu.getByRole("link", { name: "Fila" }).focus();
  await page.keyboard.press("Alt+ArrowDown");
  expect((await ordemDe()).slice(0, 5)).toEqual(["/historico", "/dashboard", "/workers", "/maquinas", "/fila"]);
  await page.locator("aside").screenshot({ path: `${TELAS}/menu-reordenado.png`, animations: "disabled" });

  await abrir(page, "/dashboard");
  await expect.poll(async () => (await ordemDe()).slice(0, 5)).toEqual(["/historico", "/dashboard", "/workers", "/maquinas", "/fila"]);

  await abrir(page, "/settings");
  await page.getByRole("button", { name: "Restaurar padrão" }).click();
  await expect.poll(async () => (await ordemDe()).slice(0, 4)).toEqual(["/dashboard", "/fila", "/maquinas", "/historico"]);
  expect(erros).toEqual([]);
});

test("menu lateral: recolher só esconde o texto; ícones e o B do logo não se mexem", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  const { erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const menu = page.locator("aside nav");
  const icone = () => menu.getByRole("link", { name: "Painel" }).locator("svg").boundingBox();
  const logo = page.getByTestId("logo-menu");
  const imagem = page.locator("aside img[alt='Biason']");
  const aberto = { icone: (await icone())!, logo: (await logo.boundingBox())!, imagem: (await imagem.boundingBox())! };
  await expect(menu.getByText("Painel", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Recolher navegação" }).click();
  // o nome fica só para leitor de tela (1px), não aparece
  await expect.poll(async () => (await menu.getByText("Painel", { exact: true }).boundingBox())!.width).toBeLessThanOrEqual(1);
  await expect.poll(async () => (await logo.boundingBox())!.width).toBeLessThan(aberto.logo.width / 3);
  const recolhido = { icone: (await icone())!, imagem: (await imagem.boundingBox())! };
  expect(recolhido.icone.width).toBeCloseTo(aberto.icone.width, 0);  // mesmo tamanho
  expect(recolhido.icone.x).toBeCloseTo(aberto.icone.x, 0);  // mesmo lugar
  expect(recolhido.imagem.x).toBeCloseTo(aberto.imagem.x, 0);  // o B não anda
  expect(recolhido.imagem.height).toBeCloseTo(aberto.imagem.height, 0);
  await page.locator("aside").screenshot({ path: `${TELAS}/menu-recolhido.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});
