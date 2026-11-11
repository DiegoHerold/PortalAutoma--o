import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Fase 8: o que a automação declara ao conectar (entradas com a origem e "fora de uso"), a
 * tabela dela em prévia para aprovar na aba Itens, a aba Arquivos com o download autenticado e
 * o prazo dos arquivos na Retenção. A API é simulada só aqui.
 */

const TELAS = "../docs/fase-8-telas";
mkdirSync(TELAS, { recursive: true });

const campo = (c: Record<string, unknown>) => ({ obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false,
  origem: "automacao", fora_de_uso: false, ...c });

const FORMULARIO = {
  origem: "portal", versao: 3, pode_editar: true,
  item: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo" },
  entrada: [
    campo({ chave: "competencia", rotulo: "Competência", tipo: "mes_ano", obrigatorio: true }),
    campo({ chave: "modo", rotulo: "O que fazer", tipo: "lista", padrao: "completo", opcoes: ["completo", "rubricas"] }),
    campo({ chave: "lote_antigo", rotulo: "Lote antigo", tipo: "texto", obrigatorio: true, fora_de_uso: true }),
    campo({ chave: "observacao", rotulo: "Observação do pedido", tipo: "texto", origem: "portal" }),
  ],
  colunas: [campo({ chave: "caminho_saida", rotulo: "Pasta de destino", tipo: "pasta" })],
  tipos: [["texto", "Texto"], ["mes_ano", "Mês/ano"], ["lista", "Lista de opções"], ["pasta", "Pasta"], ["json", "Dados avançados (JSON)"]]
    .map(([tipo, rotulo]) => ({ tipo, rotulo })),
};

const ITENS = [
  { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: { caminho_saida: "F:\\5081" }, ativo: true },
];

type Pedido = { metodo: string; caminho: string; corpo: unknown; autorizacao: string | null };

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
  let proposta: unknown = {
    recebida_em: em(-600), instancia_id: "dri_teste", total: 4,
    novos: [{ chave: "5076", rotulo: "Filial de teste", grupo: "5081", atributos: {}, ativo: true },
            { chave: "5099", rotulo: "Empresa nova de teste", grupo: null, atributos: {}, ativo: true }],
    alterados: [{ chave: "5081", rotulo: "Matriz de teste renomeada", grupo: null, atributos: {}, ativo: true, mudancas: ["rotulo"] }],
    iguais: 0, erros: [{ linha: 4, chave: "x y", campos: { chave: "use letras, números, ponto, hífen ou sublinhado (até 120)" } }],
  };
  let retencao = { automation_id: 7, automacao: "Integração Contábil · Folha", imagens_dias: null, logs_dias: 90, arquivos_dias: null as number | null };
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo, autorizacao: await req.headerValue("authorization") });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/automations/7") return json({ id: 7, name: "Integração Contábil · Folha", slug: "ic", key: "dominio.integracao_contabil", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true, description: "Integração contábil da folha na Domínio." });
    if (caminho === "/painel") return json({ gerado_em: em(0), central: true, maquinas: [], fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, execucoes: [] });
    if (caminho === "/fila") return json({ gerado_em: em(0), perdidos: [], maquinas: [], jobs: [] });
    if (caminho === "/historico") return json({ cursor: null, execucoes: [] });
    if (caminho === "/automations/7/formulario") return json(FORMULARIO);
    if (caminho === "/automations/7/itens") return json({ definicao: { nome: "Empresa", chave: "codigo", grupo: "matriz_codigo", afetam_trabalho: [] },
      pode_editar: true, contagem: { ativos: 1, total: 1 }, proximo: null, itens: ITENS });
    if (caminho === "/automations/7/itens/proposta") {
      if (req.method() === "DELETE") { proposta = null; return route.fulfill({ status: 204 }); }
      return json(proposta);
    }
    if (caminho === "/automations/7/itens/proposta/aprovar") {
      const chaves = (corpo as { chaves: string[] }).chaves;
      proposta = null;
      return json({ criados: chaves.filter((c) => c !== "5081").length, alterados: chaves.includes("5081") ? 1 : 0, iguais: 0 });
    }
    if (caminho === "/automations/7/arquivos") {
      const busca = url.searchParams.get("busca");
      const todos = [
        { id: "art_1", nome: "5081 Resumo_Rubricas_Consolidado.xlsx", tipo: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", bytes: 48213, situacao: "available", execucao_id: "exe_9", job_id: "j", item: "5081", quando: em(-3600) },
        { id: "art_2", nome: "5081 integracao 10-2026.txt", tipo: "text/plain", bytes: 912, situacao: "available", execucao_id: "exe_9", job_id: "j", item: "5081", quando: em(-3500) },
        { id: "art_3", nome: "lote 20261111-0900 resultado.csv", tipo: "text/csv", bytes: 2380000, situacao: "available", execucao_id: "exe_9", job_id: "j", item: null, quando: em(-3400) },
      ];
      return json({ arquivos: busca ? todos.filter((a) => a.nome.includes(busca) || a.item === busca) : todos, cursor: null });
    }
    if (caminho === "/automations/7/arquivos/art_2/baixar") {
      return route.fulfill({ status: 200, contentType: "text/plain", body: "linha;valor\r\n", headers: { "Content-Disposition": "attachment" } });
    }
    if (caminho === "/governance/retencao-por-automacao") return json({ limites: { minimo: 1, maximo: 3650 }, automacoes: [retencao] });
    if (caminho === "/governance/retencao-por-automacao/7") {
      retencao = { ...retencao, ...(corpo as object) };
      return json(retencao);
    }
    if (caminho === "/governance/retention-policies") return json([]);
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("entradas: origem e fora de uso; executar e a visão geral não pedem o que saiu de uso", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { erros } = await preparar(page);
  await abrir(page, "/automations/7");
  const pede = page.getByTestId("o-que-pede");
  await expect(pede.getByText("Competência *")).toBeVisible();
  await expect(pede.getByText("Empresas")).toBeVisible();
  await expect(pede.getByText("Lote antigo")).toHaveCount(0);

  await page.getByRole("button", { name: "Entradas", exact: true }).click();
  const editor = page.getByTestId("editor-de-campos");
  await expect(editor.locator("[data-campo='competencia']").getByText("da automação")).toBeVisible();
  await expect(editor.locator("[data-campo='lote_antigo']").getByText("fora de uso")).toBeVisible();
  await expect(editor.locator("[data-campo='observacao']").getByText("da automação")).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "Salvar campos" })).toBeDisabled();  // nada mudou
  await page.screenshot({ path: `${TELAS}/entradas.png`, fullPage: true, animations: "disabled" });

  await page.getByRole("button", { name: "Executar" }).first().click();
  const janela = page.getByTestId("executar");
  await expect(janela.getByLabel("Competência")).toBeVisible();
  await expect(janela.getByLabel("Observação do pedido")).toBeVisible();
  await expect(janela.getByLabel("Lote antigo")).toHaveCount(0);
  expect(erros).toEqual([]);
});

test("itens: a tabela da automação em prévia; aprovar só o escolhido", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/automations/7#itens");
  const aviso = page.getByTestId("proposta-da-automacao");
  await expect(aviso.getByText("2 novo(s), 1 alterado(s), 1 com erro", { exact: false })).toBeVisible();
  await page.screenshot({ path: `${TELAS}/itens-previa.png`, animations: "disabled" });
  await aviso.getByRole("button", { name: "Ver e aprovar" }).click();
  const detalhe = page.getByTestId("proposta-detalhe");
  await expect(detalhe.getByText("nome", { exact: true })).toBeVisible();  // o que muda no alterado, em palavras
  await expect(detalhe.getByText("Com erro (1): não entram")).toBeVisible();
  await detalhe.getByLabel("Escolher Empresa nova de teste").uncheck();
  await page.screenshot({ path: `${TELAS}/itens-aprovar.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Aprovar 2" }).click();
  await expect(aviso).toHaveCount(0);
  const aprovar = pedidos.find((p) => p.caminho === "/automations/7/itens/proposta/aprovar")!;
  expect(aprovar.metodo).toBe("POST");
  expect((aprovar.corpo as { chaves: string[] }).chaves.sort()).toEqual(["5076", "5081"]);
  expect(erros).toEqual([]);
});

test("itens: descartar a tabela da automação", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/automations/7#itens");
  await page.getByTestId("proposta-da-automacao").getByRole("button", { name: "Descartar" }).click();
  await expect(page.getByTestId("proposta-da-automacao")).toHaveCount(0);
  expect(pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/automations/7/itens/proposta")).toBe(true);
  expect(erros).toEqual([]);
});

for (const tema of ["light", "dark"] as const) {
  test(`arquivos: lista, busca e download com o token no cabeçalho — ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const { pedidos, erros } = await preparar(page, tema);
    await abrir(page, "/automations/7#arquivos");
    const lista = page.getByTestId("arquivos");
    await expect(lista.getByRole("listitem")).toHaveCount(3);
    await expect(lista.getByText("do lote", { exact: false })).toBeVisible();
    await expect(lista.getByText("2,3 MB", { exact: false })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `${TELAS}/arquivos-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
    if (tema === "dark") return expect(erros).toEqual([]);

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Baixar 5081 integracao 10-2026.txt" }).click();
    expect((await download).suggestedFilename()).toBe("5081 integracao 10-2026.txt");
    const baixar = pedidos.find((p) => p.caminho === "/automations/7/arquivos/art_2/baixar")!;
    expect(baixar.autorizacao).toBe("Bearer token-de-teste");  // nunca na URL

    await page.getByLabel("Buscar arquivo").fill("resultado");
    await expect(lista.getByRole("listitem")).toHaveCount(1);
    expect(pedidos.some((p) => p.caminho.startsWith("/automations/7/arquivos?") && p.caminho.includes("busca=resultado"))).toBe(true);
    expect(erros).toEqual([]);
  });
}

test("retenção: prazo dos arquivos entregues", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/governance/retention");
  const lista = page.getByTestId("retencao-por-automacao");
  await expect(lista.getByText("Arquivos: Sem prazo")).toBeVisible();
  await lista.getByRole("button", { name: "Definir prazos de Integração Contábil · Folha" }).click();
  await page.getByLabel("Arquivos entregues: guardar por").fill("365");
  await page.screenshot({ path: `${TELAS}/retencao-arquivos.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Salvar e apagar o que passar do prazo" }).click();
  await expect(lista.getByText("Arquivos: 365 dias")).toBeVisible();
  expect(pedidos.filter((p) => p.metodo === "PUT").map((p) => p.corpo)).toEqual([{ imagens_dias: null, logs_dias: 90, arquivos_dias: 365 }]);
  expect(erros).toEqual([]);
});
