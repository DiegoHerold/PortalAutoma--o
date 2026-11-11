import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Fase 7: a automação no Catálogo (ao vivo, fila, histórico), o botão Executar com os campos
 * da automação e o editor de campos. A API é simulada só aqui.
 */

const TELAS = "../docs/fase-7-telas";
const IMAGEM = readFileSync(path.join(__dirname, "fixtures", "tela-a.jpg"));

const FORMULARIO = {
  origem: "manifesto", versao: 0, pode_editar: true,
  item: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo" },
  entrada: [
    { chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true, padrao: null, opcoes: [], ajuda: "Mês e ano da folha (MM/AAAA).", afeta_trabalho: false },
    { chave: "modo", rotulo: "O que fazer", tipo: "lista", obrigatorio: true, padrao: "completo", opcoes: ["completo", "rubricas", "integracao"], ajuda: null, afeta_trabalho: false },
    { chave: "enviar_email", rotulo: "Avisar por e-mail no fim", tipo: "sim_nao", obrigatorio: false, padrao: true, opcoes: [], ajuda: null, afeta_trabalho: false },
  ],
  colunas: [
    { chave: "separar_por_custo", rotulo: "Separar por custo", tipo: "sim_nao", obrigatorio: false, padrao: false, opcoes: [], ajuda: null, afeta_trabalho: true },
    { chave: "caminho_saida", rotulo: "Pasta de destino", tipo: "pasta", obrigatorio: true, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false },
    { chave: "email", rotulo: "E-mail do responsável", tipo: "email", obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false },
  ],
  tipos: [["texto", "Texto"], ["texto_longo", "Texto longo"], ["numero", "Número"], ["inteiro", "Número inteiro"], ["sim_nao", "Sim ou não"],
    ["data", "Data"], ["mes_ano", "Mês/ano"], ["lista", "Lista de opções"], ["email", "E-mail"], ["pasta", "Pasta"], ["json", "Dados avançados (JSON)"]]
    .map(([tipo, rotulo]) => ({ tipo, rotulo })),
};

const ITENS = [
  { chave: "5066", rotulo: "Empresa sozinha de teste", grupo: null, atributos: { separar_por_custo: false, caminho_saida: "F:\\5066" }, ativo: true },
  { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: { separar_por_custo: true, caminho_saida: "F:\\5081", rubricas_ignoradas: [{ codigo: 450 }] }, ativo: true },
  { chave: "5076", rotulo: "Filial de teste", grupo: "5081", atributos: { separar_por_custo: false, caminho_saida: "F:\\5076" }, ativo: true },
];

type Pedido = { metodo: string; caminho: string; corpo: unknown };

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
  let formulario = structuredClone(FORMULARIO) as typeof FORMULARIO;
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/automations/7") return json({ id: 7, name: "Integração Contábil · Folha", slug: "ic", key: "dominio.integracao_contabil", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true, description: "Integração contábil da folha na Domínio." });
    if (caminho === "/automations") return json([
      { id: 7, name: "Integração Contábil · Folha", slug: "ic", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true },
      { id: 9, name: "Conferência de guias", slug: "cg", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true },
      { id: 11, name: "Automação antiga", slug: "antiga", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: false, status: "archived" }]);
    if (caminho === "/automations/11/restaurar") return json({ id: 11, name: "Automação antiga", slug: "antiga", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true, status: "active" });
    if (caminho === "/categories") return json([{ id: 1, name: "Folha", slug: "folha" }]);
    if (caminho === "/painel") return json({ gerado_em: em(0), central: true, maquinas: [], fila: { esperando: 1, perdidos: 0, termina_em: null, sem_previsao: 0 }, execucoes: [{
      execucao_id: "exe_1", job_id: "job_1", automation_id: 7, automacao: "Integração Contábil · Folha", maquina_id: "mch_1", maquina: "FOLHA-194",
      modo: "direct", itens: [{ chave: "5081", rotulo: "Matriz de teste" }], tentativa: 1, desde: em(-900), decorrido_s: 900, falta_s: 1200,
      motivo_sem_previsao: null, termino_previsto: em(1200), etapa: { etapa: "rubricas", item: "5081" }, item: { item: "5081", rotulo: "Matriz de teste" },
      progresso: { atual: 18, total: 50, rotulo: "centro 18 de 50" }, pausa: null, atencoes: 0, pode_ver_tela: true,
      tela: { imagem_id: "img_a", rotulo: "Salvou o centro", segundos_nesta_tela: 12, espera_rotulo: null, imagem: { situacao: "pronta", motivo: null } },
      log: [{ id: "l1", nivel: "info", texto: "Centro 18 de 50 conferido", item: "5081", espera: false, quando: em(-5) }] }] });
    if (/\/imagens\//.test(caminho)) return route.fulfill({ status: 200, contentType: "image/jpeg", body: IMAGEM });
    if (caminho === "/fila") return json({ gerado_em: em(0), perdidos: [], maquinas: [], jobs: [
      { posicao: 1, job_id: "job_2", execution_id: "exe_2", automation_id: 7, automacao: "Integração Contábil · Folha", pool: "tela", itens: ["5066"],
        prioridade: 0, posicao_manual: null, maquina_prevista: "mch_1", maquina_prevista_nome: "FOLHA-194", maquina_obrigatoria: null,
        inicio_previsto: em(1200), termino_previsto: em(1800), estimativa_s: 600, estimativa_minima_s: null, etapas_sem_base: [], motivos: [], enfileirado_em: em(-60) },
      { posicao: 2, job_id: "job_3", execution_id: "exe_3", automation_id: 9, automacao: "Conferência de guias", pool: "tela", itens: ["7310"],
        prioridade: 0, posicao_manual: null, maquina_prevista: null, maquina_prevista_nome: null, maquina_obrigatoria: null,
        inicio_previsto: null, termino_previsto: null, estimativa_s: null, estimativa_minima_s: null, etapas_sem_base: [], motivos: [], enfileirado_em: em(-30) }] });
    if (caminho === "/historico") return json({ cursor: null, execucoes: [
      { execucao_id: "exe_9", status: "succeeded", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5081", "5076"], total_itens: 2, maquinas: "FOLHA-194", iniciada_em: em(-9000), concluida_em: em(-7400), duracao_s: 1600, previsto_s: 1500, falha: null },
      { execucao_id: "exe_8", status: "failed", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5066"], total_itens: 1, maquinas: "FOLHA-194", iniciada_em: em(-12000), concluida_em: em(-11000), duracao_s: 1000, previsto_s: 600, falha: "Rubricas: o Total não bateu" }] });
    if (caminho === "/automations/7/formulario") {
      if (req.method() === "PUT") {
        formulario = { ...formulario, ...corpo, origem: "portal", versao: formulario.versao + 1 };
        return json(formulario);
      }
      return json(formulario);
    }
    if (caminho === "/automations/7/itens") return json({ definicao: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo", afetam_trabalho: ["separar_por_custo"] },
      pode_editar: true, contagem: { ativos: 3, total: 3 }, proximo: null, itens: ITENS });
    if (caminho === "/automations/7/itens/5081" && req.method() === "PUT") {
      const pasta = (corpo as { atributos: Record<string, unknown> }).atributos.caminho_saida;
      return pasta ? json({ ...ITENS[1], ...(corpo as object) }) : json({ error: { code: "VALIDATION_ERROR", message: "inválido", details: { campos: { "atributos.caminho_saida": "obrigatório" } } } }, 422);
    }
    if (caminho === "/automations/7/itens/pedir-execucao") {
      const parametros = (corpo as { parametros: Record<string, unknown> }).parametros;
      if (!parametros.competencia) return json({ error: { code: "VALIDATION_ERROR", message: "inválido", details: { campos: { competencia: "obrigatório" } } } }, 422);
      return json({ execution_id: "exe_x", jobs: [{ job_id: "j", existente: false }], itens: ["5081", "5076"] }, 201);
    }
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
  test(`automação: ao vivo, na fila e últimas execuções — ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    const { erros } = await preparar(page, tema);
    await abrir(page, "/automations/7");
    await expect(page.getByRole("heading", { name: "Integração Contábil · Folha" })).toBeVisible();
    await expect(page.getByText("Rodando agora")).toBeVisible();
    await expect(page.getByTestId("rodando-agora").getByTestId("monitor")).toHaveCount(1);
    await expect(page.getByTestId("na-fila").getByRole("listitem")).toHaveCount(1);  // só os desta automação
    await expect(page.getByText("Rubricas: o Total não bateu").or(page.getByText("Falhou")).first()).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `${TELAS}/automacao-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
    expect(erros).toEqual([]);
  });
}

test("executar: escolher empresas, informações pelos campos, erro ao lado do campo", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/automations/7");
  await page.getByRole("button", { name: "Executar" }).first().click();
  const janela = page.getByTestId("executar");
  await expect(janela.getByLabel("O que fazer")).toHaveValue("completo");  // padrão do campo
  await expect(janela.getByLabel("Avisar por e-mail no fim")).toBeChecked();
  await janela.getByLabel("Escolher Matriz de teste").check();
  await expect(page.getByRole("button", { name: "Executar 2 empresa(s)" })).toBeEnabled();  // a matriz e a filial
  await page.getByRole("button", { name: "Executar 2 empresa(s)" }).click();
  await expect(janela.getByRole("alert").filter({ hasText: "obrigatório" })).toBeVisible();
  await janela.getByLabel("Competência").fill("10/2026");
  await page.screenshot({ path: `${TELAS}/executar.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Executar 2 empresa(s)" }).click();
  await expect(janela).toHaveCount(0);
  const enviados = pedidos.filter((p) => p.caminho.startsWith("/automations/7/itens/pedir-execucao")).map((p) => p.corpo);
  expect(enviados.at(-1)).toEqual({ chaves: ["5081"], com_filiais: true,
    parametros: { competencia: "10/2026", modo: "completo", enviar_email: true } });
  expect(erros.filter((e) => !e.includes("422"))).toEqual([]);
});

test("campos: criar, ordenar e salvar; o pedido seguinte usa o campo novo", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/automations/7#campos");
  const editor = page.getByTestId("editor-de-campos");
  await expect(editor.getByText("Hoje valem os campos sugeridos pela automação", { exact: false })).toBeVisible();
  await editor.getByRole("button", { name: "Novo campo" }).first().click();
  const novo = editor.locator("[data-campo]").nth(3);
  await novo.getByLabel("Nome do campo").fill("Responsável pela conferência");
  await expect(novo.getByText("responsavel_pela_conferencia")).toBeVisible();
  await novo.getByLabel("Tipo do campo").selectOption("email");
  await novo.getByLabel("Obrigatório").check();
  await editor.locator("[data-campo='enviar_email']").getByRole("button", { name: "Descer" }).click();
  await page.screenshot({ path: `${TELAS}/campos.png`, fullPage: true, animations: "disabled" });
  await editor.getByRole("button", { name: "Salvar campos" }).click();
  await expect(editor.getByText("o que você muda aqui continua valendo", { exact: false })).toBeVisible();
  const salvo = pedidos.find((p) => p.metodo === "PUT" && p.caminho.startsWith("/automations/7/formulario"))!.corpo as {
    entrada: Array<{ chave: string; tipo: string; obrigatorio: boolean }>; versao: number };
  expect(salvo.versao).toBe(0);
  expect(salvo.entrada.map((c) => c.chave)).toEqual(["competencia", "modo", "responsavel_pela_conferencia", "enviar_email"]);
  expect(salvo.entrada[2]).toMatchObject({ tipo: "email", obrigatorio: true });
  // a janela Executar já pede o campo novo
  await page.getByRole("button", { name: "Executar" }).first().click();
  await expect(page.getByTestId("executar").getByLabel("Responsável pela conferência")).toBeVisible();
  expect(erros).toEqual([]);
});

test("itens: editar usa as colunas da automação e mostra o erro no campo", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations/7#itens");
  await page.getByRole("button", { name: "Editar Matriz de teste" }).click();
  const form = page.getByTestId("editar-item");
  await expect(form.getByLabel("Pasta de destino")).toHaveValue("F:\\5081");
  await expect(form.getByLabel("Separar por custo")).toBeChecked();
  await expect(form.getByText("Também guardado (sem coluna)", { exact: false })).toBeVisible();
  await form.getByLabel("Pasta de destino").fill("");
  await page.getByRole("button", { name: "Salvar" }).click();
  await expect(form.getByText("obrigatório")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/editar-item.png`, animations: "disabled" });
  expect(erros.filter((e) => !e.includes("422"))).toEqual([]);
});

test("catálogo: a automação que está rodando aparece com o selo", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations");
  await expect(page.getByTestId("rodando")).toHaveCount(1);
  await page.screenshot({ path: `${TELAS}/catalogo.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});


test("catálogo: arquivada sai da lista, fica em Arquivadas e volta ao restaurar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/automations");
  await expect(page.getByText("Integração Contábil · Folha")).toBeVisible();
  await expect(page.getByText("Automação antiga")).toHaveCount(0);
  await page.getByRole("button", { name: "Arquivadas (1)" }).click();
  await expect(page.getByText("Automação antiga")).toBeVisible();
  await expect(page.getByText("Arquivada", { exact: true })).toBeVisible();
  await expect(page.getByText("Integração Contábil · Folha")).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/arquivadas.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Restaurar" }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "POST" && p.caminho === "/automations/11/restaurar")).toBe(true);
  expect(erros).toEqual([]);
});
