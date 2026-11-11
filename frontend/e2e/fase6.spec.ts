import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Fase 6: sino de avisos, preferências de notificação, retenção por automação e as telas
 * administrativas no visual novo. A API é simulada só aqui.
 */

const TELAS = "../docs/fase-6-telas";

type Pedido = { metodo: string; caminho: string; corpo: unknown };

async function preparar(page: Page, { papel = "admin", tema = "light" }: { papel?: string; tema?: "light" | "dark" } = {}) {
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
  let lidas = false;
  let prazos: Record<number, { imagens_dias: number | null; logs_dias: number | null }> = { 9: { imagens_dias: 30, logs_dias: 90 } };
  let pref = { tipos: ["erro"], fila_minutos: 30 };
  const gestor = papel === "admin";
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: papel, permissions: [], rbac_permissions: gestor ? ["admin.system"] : [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/notificacoes/lidas") { lidas = true; return json({ marcadas: 2 }); }
    if (caminho === "/notificacoes") return json({ nao_lidas: lidas ? 0 : 2, avisos: [
      { id: "ntd_1", tipos: ["erro", "termino"], titulo: "Integração Contábil · Folha: terminou com erro", texto: "A execução exe_8 terminou com erro. Motivo: Rubricas: o Total não bateu", link: "/execucoes/exe_8", quando: em(-120), lida: lidas, email: "pendente" },
      { id: "ntd_2", tipos: ["maquina_offline"], titulo: "Máquina FOLHA-02 offline", texto: "A máquina FOLHA-02 parou de dar sinal às 14:55 (UTC).", link: "/maquinas", quando: em(-900), lida: lidas, email: "pendente" },
      { id: "ntd_3", tipos: ["termino"], titulo: "Conferência de guias: concluída", texto: "A execução exe_7 terminou.", link: "/execucoes/exe_7", quando: em(-7200), lida: true, email: "pendente" },
    ] });
    if (caminho === "/notificacoes/preferencias") {
      if (req.method() === "PUT") pref = corpo;
      const disponiveis = [
        { tipo: "erro", rotulo: "Erro numa execução", so_gestores: false },
        { tipo: "atencao", rotulo: "Item aguardando uma pessoa", so_gestores: false },
        ...(gestor ? [{ tipo: "maquina_offline", rotulo: "Máquina offline", so_gestores: true }, { tipo: "fila_parada", rotulo: "Fila parada", so_gestores: true }] : []),
        { tipo: "termino", rotulo: "Término de execução", so_gestores: false },
      ];
      return json({ ...pref, email: "operador@teste.invalid", disponiveis, fila_minutos_limites: [5, 1440], envio_por_email: "desligado" });
    }
    if (caminho === "/governance/retencao-por-automacao") return json({ limites: { minimo: 1, maximo: 3650 }, automacoes: [
      { automation_id: 7, automacao: "Integração Contábil · Folha", imagens_dias: prazos[7]?.imagens_dias ?? null, logs_dias: prazos[7]?.logs_dias ?? null },
      { automation_id: 9, automacao: "Conferência de guias", imagens_dias: prazos[9]?.imagens_dias ?? null, logs_dias: prazos[9]?.logs_dias ?? null },
    ] });
    const prazo = caminho.match(/^\/governance\/retencao-por-automacao\/(\d+)$/);
    if (prazo) { prazos = { ...prazos, [Number(prazo[1])]: corpo }; return json({ automation_id: Number(prazo[1]), ...corpo }); }
    if (caminho === "/governance/retention-policies") return json([
      { organization_id: null, resource_type: "ExecutionLog", retention_days: 30, archive_after_days: 15, delete_after_days: 90, legal_hold: false, enabled: true, updated_at: em(-86400) },
      { organization_id: null, resource_type: "AuditEvent", retention_days: 365, archive_after_days: null, delete_after_days: null, legal_hold: true, enabled: true, updated_at: em(-86400) },
    ]);
    if (caminho === "/roles") return json([
      { id: 1, name: "Administrador", slug: "admin", description: "Acesso total ao portal." },
      { id: 2, name: "Operador", slug: "operator", description: "Executa e acompanha as automações liberadas." },
    ]);
    if (caminho === "/painel") return json({ gerado_em: em(0), central: true, execucoes: [], maquinas: [], fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 } });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("sino: avisos por ler, lista e marcar como lidos", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/dashboard");
  await expect(page.getByTestId("avisos-por-ler")).toHaveText("2");
  await page.getByRole("button", { name: "Avisos: 2 por ler" }).click();
  const caixa = page.getByRole("dialog", { name: "Avisos" });
  await expect(caixa.getByText("Integração Contábil · Folha: terminou com erro")).toBeVisible();
  await expect(caixa.getByText("Máquina FOLHA-02 offline")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/sino-de-avisos.png`, animations: "disabled" });
  await caixa.getByRole("button", { name: "Marcar todos como lidos" }).click();
  await expect(page.getByTestId("avisos-por-ler")).toHaveCount(0);
  expect(pedidos.filter((p) => p.caminho === "/notificacoes/lidas").map((p) => p.corpo)).toEqual([{}]);
  expect(erros).toEqual([]);
});

test("notificações: cada pessoa escolhe; fila parada pede o tempo; e-mail desligado é dito", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/settings#notificacoes");
  const bloco = page.getByTestId("notificacoes");
  await expect(bloco.getByText("O envio por e-mail ainda não está ligado no portal.", { exact: false })).toBeVisible();
  await expect(bloco.getByLabel("Erro numa execução")).toBeChecked();
  await bloco.getByLabel("Fila parada").check();
  await bloco.getByLabel("Minutos da fila parada").fill("45");
  await bloco.getByLabel("Término de execução").check();
  await page.getByTestId("notificacoes").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${TELAS}/notificacoes-preferencias.png`, animations: "disabled" });
  await bloco.getByRole("button", { name: "Salvar notificações" }).click();
  await expect.poll(() => pedidos.filter((p) => p.metodo === "PUT" && p.caminho === "/notificacoes/preferencias").map((p) => p.corpo))
    .toEqual([{ tipos: ["erro", "fila_parada", "termino"], fila_minutos: 45 }]);
  expect(erros).toEqual([]);
});

test("notificações: quem não é gestor não vê máquina offline nem fila parada", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { erros } = await preparar(page, { papel: "operator" });
  await abrir(page, "/settings#notificacoes");
  const bloco = page.getByTestId("notificacoes");
  await expect(bloco.getByLabel("Término de execução")).toBeVisible();
  await expect(bloco.getByLabel("Máquina offline")).toHaveCount(0);
  await expect(bloco.getByLabel("Fila parada")).toHaveCount(0);
  expect(erros).toEqual([]);
});

for (const tema of ["light", "dark"] as const) {
  test(`retenção por automação: sem prazo nada sai; encurtar avisa que apaga — ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    const { pedidos, erros } = await preparar(page, { tema });
    await abrir(page, "/governance/retention");
    const lista = page.getByTestId("retencao-por-automacao");
    await expect(lista.getByText("Imagens: Sem prazo")).toBeVisible();
    await expect(lista.getByText("Imagens: 30 dias")).toBeVisible();
    await expect(page.getByText("Hoje estas políticas não apagam nada sozinhas", { exact: false })).toBeVisible();
    await page.screenshot({ path: `${TELAS}/retencao-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
    if (tema === "dark") return expect(erros).toEqual([]);

    await lista.getByRole("button", { name: "Definir prazos de Integração Contábil · Folha" }).click();
    await page.getByLabel("Imagens das telas: guardar por").fill("0");
    await expect(page.getByText("Use um número inteiro de 1 a 3650 dias")).toBeVisible();
    await page.getByLabel("Imagens das telas: guardar por").fill("30");
    await expect(page.getByRole("alert").getByText("apagado de vez", { exact: false })).toBeVisible();
    await page.screenshot({ path: `${TELAS}/retencao-confirmar.png`, animations: "disabled" });
    await page.getByRole("button", { name: "Salvar e apagar o que passar do prazo" }).click();
    await expect(lista.getByText("Imagens: 30 dias")).toHaveCount(2);
    expect(pedidos.filter((p) => p.metodo === "PUT").map((p) => [p.caminho, p.corpo])).toEqual([
      ["/governance/retencao-por-automacao/7", { imagens_dias: 30, logs_dias: null, arquivos_dias: null }]]);
    expect(erros).toEqual([]);
  });
}

for (const tela of [
  { rota: "/roles", nome: "papeis" },
  { rota: "/secrets", nome: "segredos" },
  { rota: "/service-accounts", nome: "contas-de-servico" },
  { rota: "/teams", nome: "times" },
  { rota: "/governance/limits", nome: "limites" },
]) {
  test(`tela administrativa no visual novo: ${tela.nome}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const { erros } = await preparar(page);
    await abrir(page, tela.rota);
    await expect(page.locator("h1")).toBeVisible();
    // sem texto sem acento comum
    const corpo = await page.locator("main").innerText();
    expect(corpo).not.toMatch(/\b(Voce|nao|politica|permissao|retencao|execucao|organizacao)\b/);
    await page.screenshot({ path: `${TELAS}/admin-${tela.nome}.png`, animations: "disabled" });
    expect(erros).toEqual([]);
  });
}

test("resposta fora do formato nas notificações não derruba as Configurações", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { erros } = await preparar(page);
  await page.route(`${API_DE_TESTE}/notificacoes/preferencias`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route(`${API_DE_TESTE}/notificacoes?limite=20`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
  await abrir(page, "/settings#notificacoes");
  await expect(page.getByText("Não foi possível carregar as notificações.")).toBeVisible();
  await page.getByRole("button", { name: "Menu e atalhos" }).click();
  await expect(page.getByRole("heading", { name: "Menu e atalhos" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Avisos" })).toBeVisible();
  expect(erros).toEqual([]);
});


test("configurações: tudo alcançável, o que sai do menu continua nas Configurações; abas pelo endereço", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { erros } = await preparar(page);
  await abrir(page, "/settings");
  const areas = page.getByTestId("areas-do-portal");
  const menu = page.locator("aside nav");
  // tira um item padrão do menu: ele some do menu e continua nas Configurações, com o atalho
  await areas.getByLabel("Mostrar Fluxos no menu").uncheck();
  await expect(menu.getByRole("link", { name: "Fluxos" })).toHaveCount(0);
  await expect(areas.getByRole("link", { name: "Fluxos" })).toBeVisible();
  await expect(areas.getByText("Fora do menu").first()).toBeVisible();
  // liga um item que vinha fora: aparece no menu, na categoria dele, e continua nas Configurações
  await areas.getByLabel("Mostrar Retenção no menu").check();
  await expect(menu.getByRole("link", { name: "Retenção" })).toBeVisible();
  await expect(menu.locator("[data-grupo='Governança']")).toBeVisible();
  await expect(areas.getByRole("link", { name: "Retenção" })).toBeVisible();
  await page.screenshot({ path: `${TELAS}/configuracoes-menu.png`, fullPage: true, animations: "disabled" });
  await areas.getByRole("link", { name: "Fluxos" }).click();
  await expect(page).toHaveURL(/\/flows$/);

  for (const [aba, titulo] of [["conta", "Sua conta"], ["sistema", "Sistema"], ["notificacoes", "Notificações"]] as const) {
    await abrir(page, `/settings#${aba}`);
    await expect(page.getByRole("heading", { name: titulo, exact: true })).toBeVisible();
    if (aba === "conta") await expect(page.getByText("Administrador", { exact: true })).toBeVisible();  // papel em português
    await page.screenshot({ path: `${TELAS}/configuracoes-${aba}.png`, fullPage: true, animations: "disabled" });
  }
  expect(erros).toEqual([]);
});
