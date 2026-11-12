import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Histórico (resumo do período, execuções por dia, "Quanto tempo leva" por item) e Auditoria como
 * linha do tempo (agrupar por dia/pessoa/ação, clicar no evento e ver ao lado o que veio junto,
 * clicar na pessoa e ver só ela). API simulada só aqui.
 */

const TELAS = "../docs/historico-auditoria-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; busca: URLSearchParams; corpo: unknown };

function eventos(agora: number) {
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  const base = { antes: null, depois: null, detalhes: {}, ip: "192.168.1.50", navegador: "Chrome", ator_email: null };
  const ti = { tipo_de_ator: "user", ator_id: "5", ator_nome: "Equipe de TI", ator_email: "ti@teste.invalid" };
  const ana = { tipo_de_ator: "user", ator_id: "6", ator_nome: "Ana Souza", ator_email: "ana@teste.invalid" };
  return [
    { ...base, ...ti, id: "ev_1", quando: em(-60), acao: "maquina.cadastrada", tipo: "alteracao", recurso_tipo: "machine", recurso_id: "mch_7",
      depois: { nome: "MAQ200", sistema: "windows" }, correlacao: "c1" },
    { ...base, ...ti, id: "ev_1b", quando: em(-60), acao: "api.post", tipo: "alteracao", recurso_tipo: "maquinas", recurso_id: "-",
      detalhes: { metodo: "POST", caminho: "/api/v1/maquinas", rota: "/maquinas", status: 201, duracao_ms: 42 }, correlacao: "c1", tecnico: true },
    { ...base, ...ti, id: "ev_2", quando: em(-120), acao: "automation.updated", tipo: "alteracao", recurso_tipo: "automation", recurso_id: "7",
      antes: { name: "Folha" }, depois: { name: "Integração Contábil · Folha" }, correlacao: "c0" },
    { ...base, ...ana, id: "ev_3", quando: em(-180), acao: "login_succeeded", tipo: "acesso", recurso_tipo: "user", recurso_id: "6", correlacao: "c2" },
    { ...base, ...ti, id: "ev_4", quando: em(-86_400), acao: "user_permissions_updated", tipo: "alteracao", recurso_tipo: "user", recurso_id: "6",
      antes: { permissions: ["ver_execucoes"] }, depois: { permissions: ["ver_execucoes", "executar"] }, correlacao: "c3" },
    { ...base, tipo_de_ator: "system", ator_id: null, ator_nome: null, id: "ev_5", quando: em(-86_500), acao: "retencao.aplicada", tipo: "sistema",
      recurso_tipo: "retencao", recurso_id: "-", detalhes: { apagados: 12 }, correlacao: null },
    { ...base, ...ana, id: "ev_6", quando: em(-86_600), acao: "login_succeeded", tipo: "acesso", recurso_tipo: "user", recurso_id: "6", correlacao: "c4" },
  ];
}

async function preparar(page: Page) {
  const pedidos: Pedido[] = [];
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
  const todos = eventos(agora);
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const q = url.searchParams;
    pedidos.push({ metodo: req.method(), caminho, busca: q, corpo: req.postData() ? JSON.parse(req.postData()!) : null });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "gestor@teste.invalid", name: "Gestor de Teste", role: "admin", permissions: [], rbac_permissions: ["audit.read"] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/governance/auditoria/pessoas") return json({ pessoas: [
      { id: "6", nome: "Ana Souza", email: "ana@teste.invalid" }, { id: "5", nome: "Equipe de TI", email: "ti@teste.invalid" }] });
    // Filtra como o servidor: o registro técnico (api.*) só aparece quando se pede a mesma ação ou "técnicos".
    const filtrados = todos.filter((e) => {
      if ("tecnico" in e && !q.get("correlacao") && q.get("tecnicos") !== "true") return false;
      if (q.get("usuario") && e.ator_id !== q.get("usuario")) return false;
      if (q.get("tipo") && e.tipo !== q.get("tipo")) return false;
      if (q.get("acao") && e.acao !== q.get("acao")) return false;
      if (q.get("correlacao") && e.correlacao !== q.get("correlacao")) return false;
      if (q.get("recurso_tipo") && (e.recurso_tipo !== q.get("recurso_tipo") || e.recurso_id !== q.get("recurso_id"))) return false;
      return true;
    });
    if (caminho === "/governance/auditoria/eventos") return json({ eventos: filtrados, cursor: null });
    if (caminho === "/governance/auditoria/grupos") {
      const por = q.get("por") ?? "dia";
      const mapa = new Map<string, number>();
      for (const e of filtrados) {
        const d = new Date(e.quando);
        const k = por === "acao" ? e.acao : por === "usuario" ? (e.ator_id ?? "-")
          : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        mapa.set(k, (mapa.get(k) ?? 0) + 1);
      }
      return json({ por, grupos: [...mapa].map(([chave, total]) => ({ chave, total, ultimo: null })) });
    }
    if (caminho === "/automations") return json([{ id: 7, name: "Integração Contábil · Folha", slug: "ic", category_id: 1 }]);
    if (caminho === "/historico/resumo") return json({ dias: Number(q.get("dias")), total: 3, concluidas: 2, com_falha: 1, canceladas: 0, duracao_media_s: 1100 });
    if (caminho === "/historico") return json({ cursor: null, execucoes: [
      { execucao_id: "exe_9", status: "succeeded", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5081", "5076"], total_itens: 2,
        maquinas: "FOLHA-01", iniciada_em: em(-2000), concluida_em: em(-200), duracao_s: 1800, previsto_s: 1200, falha: null },
      { execucao_id: "exe_8", status: "failed", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5066"], total_itens: 1,
        maquinas: "FOLHA-02", iniciada_em: em(-3600), concluida_em: em(-3000), duracao_s: 600, previsto_s: 600, falha: "Rubricas: o Total não bateu" },
      { execucao_id: "exe_7", status: "succeeded", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5081"], total_itens: 1,
        maquinas: "FOLHA-01", iniciada_em: em(-90_000), concluida_em: em(-89_000), duracao_s: 1000, previsto_s: 1000, falha: null },
    ] });
    if (caminho === "/automations/7/itens") return json({ definicao: null, pode_editar: false, contagem: { ativos: 3, total: 3 }, proximo: null, itens: [
      { chave: "5066", rotulo: "Empresa sozinha de teste", grupo: null, atributos: {}, ativo: true },
      { chave: "5081", rotulo: "Matriz de teste", grupo: null, atributos: {}, ativo: true },
      { chave: "5076", rotulo: "Filial de teste", grupo: "5081", atributos: {}, ativo: true }] });
    if (caminho === "/automations/7/tempos") return json({ etapas: [
      { etapa: "abrir", nome: "Abrir a Domínio", base: "automacao", execucoes: 12, tipico_s: 90, por_tarefa_s: null, ultimo_s: 85, quando: em(-200), falhas: 0 },
      { etapa: "folha", nome: "Integrar a folha", base: "item", execucoes: 8, tipico_s: 600, por_tarefa_s: 20, ultimo_s: 780, quando: em(-200), falhas: 1 },
      { etapa: "conferir", nome: "Conferir rubricas", base: "item", execucoes: 0, tipico_s: null, por_tarefa_s: null, ultimo_s: null, quando: null, falhas: 0 },
    ] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("histórico: resumo do período, execuções por dia e filtros escondidos", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/historico");
  const resumo = page.getByTestId("resumo-historico");
  await expect(resumo).toContainText("3");
  await expect(resumo).toContainText("Com falha");
  const lista = page.getByTestId("historico");
  await expect(lista.getByRole("listitem")).toHaveCount(3);
  await expect(lista.locator("h2").first()).toContainText("Hoje");
  await expect(lista.locator("h2").nth(1)).toContainText("Ontem");
  // Comparação com o previsto em palavras, e o motivo da falha na própria linha.
  await expect(lista.locator("[data-execucao='exe_9']")).toContainText("acima do previsto");
  await expect(lista.locator("[data-execucao='exe_8']")).toContainText("Rubricas: o Total não bateu");
  await expect(page.getByLabel("Situação")).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/historico-1920.png`, fullPage: true, animations: "disabled" });

  await page.getByRole("button", { name: "30 dias" }).click();
  await expect.poll(() => pedidos.some((p) => p.caminho === "/historico" && p.busca.get("dias") === "30")).toBe(true);
  await expect.poll(() => pedidos.some((p) => p.caminho === "/historico/resumo" && p.busca.get("dias") === "30")).toBe(true);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Situação").getByRole("button", { name: "Com falha" }).click();
  await expect.poll(() => pedidos.some((p) => p.caminho === "/historico" && p.busca.get("situacao") === "failed")).toBe(true);
  await expect(page.getByRole("button", { name: "Filtros (1)" })).toBeVisible();
  expect(erros).toEqual([]);
});

test("histórico: quanto tempo leva, escolhendo a automação e o item da lista", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/historico");
  await page.getByRole("tab", { name: "Quanto tempo leva" }).click();
  await expect(page).toHaveURL(/aba=tempos/);
  await expect(page.getByText("Escolha a automação e um item")).toBeVisible();
  await page.getByLabel("Automação").selectOption("7");
  const itens = page.getByRole("listbox", { name: "Itens" });
  await expect(itens.getByRole("option")).toHaveCount(3);
  await page.getByLabel("Filtrar itens").fill("matriz");
  await expect(itens.getByRole("option")).toHaveCount(1);
  await itens.getByRole("option").getByRole("button").click();
  const card = page.getByTestId("tempos-do-item");
  await expect(card).toContainText("Matriz de teste");
  await expect(card).toContainText("Costuma levar, somando as etapas");
  await expect(card.getByRole("listitem")).toHaveCount(3);
  await expect(card).toContainText("sem histórico");
  await expect(card).toContainText("1 com falha");
  await page.screenshot({ path: `${TELAS}/historico-tempos-1920.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("auditoria: linha do tempo por dia, clique no evento mostra o que mudou e o que veio junto", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/audit");
  // Abrir uma tela não é registrado (detalhe demais para a auditoria).
  await page.waitForTimeout(500);
  expect(pedidos.filter((p) => p.metodo === "POST")).toEqual([]);

  const feed = page.getByTestId("auditoria");
  await expect(feed.locator("[data-evento]")).toHaveCount(6); // o técnico (api.post) fica escondido
  await expect(feed.locator("section h2").first()).toContainText("Hoje");
  await expect(feed.locator("section h2").nth(1)).toContainText("Ontem");
  await expect(feed).toContainText("Equipe de TI cadastrou a máquina mch_7");
  await expect(feed).toContainText("alterou as permissões do usuário Ana Souza");
  await expect(feed.locator("[data-evento]").first()).toContainText("ET");
  await expect(feed).toContainText("alterou a automação 7");
  await expect(feed).toContainText("Portal apagou o que passou do prazo de retenção");

  await feed.getByText("cadastrou a máquina").click();
  const detalhe = page.getByTestId("detalhe-auditoria");
  await expect(detalhe).toContainText("Criado com");
  await expect(detalhe).toContainText("MAQ200");
  await expect(detalhe).toContainText("192.168.1.50");
  await page.screenshot({ path: `${TELAS}/auditoria-detalhe-1920.png`, fullPage: true, animations: "disabled" });

  await detalhe.getByRole("tab", { name: "Na mesma ação" }).click();
  const rel = detalhe.getByTestId("relacionados");
  await expect(rel.getByRole("listitem")).toHaveCount(2);
  await expect(rel).toContainText("fez uma alteração em Máquinas");

  await detalhe.getByRole("tab", { name: "Da pessoa" }).click();
  await expect(rel.getByRole("listitem")).toHaveCount(3); // TI: máquina, automação e permissões
  await expect(rel).toContainText("alterou as permissões do usuário");

  await detalhe.getByRole("tab", { name: "Do item" }).click();
  await expect(rel.getByRole("listitem")).toHaveCount(1);
  // Clicar num relacionado abre ele no painel.
  await detalhe.getByRole("tab", { name: "Da pessoa" }).click();
  await rel.getByText("alterou as permissões do usuário").click();
  await expect(detalhe.getByRole("tab", { name: "O que foi" })).toHaveAttribute("aria-selected", "true");
  await expect(detalhe).toContainText("O que mudou");
  await expect(detalhe).toContainText("executar");
  expect(erros).toEqual([]);
});

test("auditoria: clique na pessoa mostra só ela; agrupar por pessoa e por ação; filtro de tipo", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, "/audit");
  const feed = page.getByTestId("auditoria");
  await expect(feed.locator("[data-evento]")).toHaveCount(6);

  await feed.getByRole("button", { name: "Equipe de TI", exact: true }).first().click();
  await expect(page).toHaveURL(/usuario=5/);
  await expect(page.getByTestId("filtro-pessoa")).toContainText("Equipe de TI");
  await expect(feed.locator("[data-evento]")).toHaveCount(3);
  await page.screenshot({ path: `${TELAS}/auditoria-pessoa-1920.png`, fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Tirar o filtro de pessoa" }).click();
  await expect(feed.locator("[data-evento]")).toHaveCount(6);

  await page.getByRole("group", { name: "Agrupar por" }).getByRole("button", { name: "Pessoa" }).click();
  await expect(page).toHaveURL(/por=usuario/);
  await expect(feed.locator("[data-grupo-auditoria]")).toHaveCount(3); // TI, Ana e o Portal
  await expect(feed.locator("[data-grupo-auditoria='5'] h2")).toContainText("3 evento(s)");
  await page.screenshot({ path: `${TELAS}/auditoria-por-pessoa-1920.png`, fullPage: true, animations: "disabled" });

  await page.getByRole("group", { name: "Agrupar por" }).getByRole("button", { name: "Ação" }).click();
  await expect(feed.locator("[data-grupo-auditoria='login_succeeded'] h2")).toContainText("Entrou no Portal");
  await feed.locator("[data-grupo-auditoria='login_succeeded']").getByRole("button", { name: "ver só esta ação" }).click();
  await expect(page).toHaveURL(/acao=login_succeeded/);
  await expect(feed.locator("[data-evento]")).toHaveCount(2);
  await page.getByRole("button", { name: "Tirar o filtro de ação" }).click();

  await page.getByRole("group", { name: "Tipo" }).getByRole("button", { name: "Alterações" }).click();
  await expect(feed.locator("[data-evento]")).toHaveCount(3);
  expect(erros).toEqual([]);
});
