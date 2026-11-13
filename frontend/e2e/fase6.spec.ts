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
  let limpeza: Record<string, number | null> = { notificacoes: 7 };
  let limites: Record<string, number> = { "execution.max_concurrent": 20 };
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
    if (caminho === "/governance/limpeza") return json({ grupos: ["Avisos", "Máquinas", "Guardado sempre"], itens: [
      { chave: "notificacoes", grupo: "Avisos", nome: "Notificações", descricao: "Avisos do sino.", o_que_sai: "Notificações mais antigas que o prazo.",
        padrao_dias: 7, minimo_dias: 2, maximo_dias: 365, editavel: true, dias: limpeza.notificacoes, personalizado: limpeza.notificacoes !== 7,
        atualizado_por: null, atualizado_em: null, ultima_limpeza_em: em(-600), ultima_limpeza_apagados: 3, total_apagados: 42 },
      { chave: "maquinas.recursos", grupo: "Máquinas", nome: "Medições de CPU, memória e disco", descricao: "Medições dos Agents.",
        o_que_sai: "Medições antigas. A última de cada Agent fica.", padrao_dias: 7, minimo_dias: 1, maximo_dias: 365, editavel: true,
        dias: 7, personalizado: false, atualizado_por: null, atualizado_em: null, ultima_limpeza_em: null, ultima_limpeza_apagados: null, total_apagados: 0 },
      { chave: "sempre.auditoria", grupo: "Guardado sempre", nome: "Auditoria", descricao: "Quem fez o quê e quando.", o_que_sai: "Nada.",
        padrao_dias: null, minimo_dias: 0, maximo_dias: 3650, editavel: false, dias: null, personalizado: false,
        atualizado_por: null, atualizado_em: null, ultima_limpeza_em: null, ultima_limpeza_apagados: null, total_apagados: 0 },
    ] });
    const regra = caminho.match(/^\/governance\/limpeza\/(.+)$/);
    if (regra) { limpeza = { ...limpeza, [regra[1]]: corpo.voltar_ao_padrao ? 7 : corpo.dias }; return json({}); }
    if (caminho === "/governance/limites") return json({ grupos: ["Execuções", "Máquinas"], itens: [
      { chave: "execution.max_concurrent", grupo: "Execuções", nome: "Execuções ao mesmo tempo", descricao: "Quantos jobs rodam juntos.",
        unidade: "quantidade", padrao: 20, minimo: 1, maximo: 500, onde_vale: "Entrega da fila às máquinas.", origem: "portal",
        variavel_de_ambiente: null, valor: limites["execution.max_concurrent"], personalizado: limites["execution.max_concurrent"] !== 20, atualizado_em: null },
      { chave: "execution.max_timeout_seconds", grupo: "Execuções", nome: "Tempo máximo de uma execução", descricao: "Teto do tempo limite.",
        unidade: "segundos", padrao: 14400, minimo: 60, maximo: 604800, onde_vale: "Montagem do job.", origem: "portal",
        variavel_de_ambiente: null, valor: 14400, personalizado: false, atualizado_em: null },
      { chave: "gateway.max_message_bytes", grupo: "Máquinas", nome: "Tamanho máximo de mensagem do Agent", descricao: "Maior mensagem do Agent.",
        unidade: "bytes", padrao: 65536, minimo: 1024, maximo: 10485760, onde_vale: "Canal com os Agents.", origem: "arquivo",
        variavel_de_ambiente: "AGENT_GATEWAY_MAX_MESSAGE_BYTES", valor: 65536, personalizado: false, atualizado_em: null },
    ] });
    const limite = caminho.match(/^\/governance\/limites\/(.+)$/);
    if (limite) { limites = { ...limites, [limite[1]]: corpo.valor }; return json({}); }
    if (caminho === "/roles") return json([
      { id: 1, name: "Administrador", slug: "admin", description: "Acesso total ao portal." },
      { id: 2, name: "Operador", slug: "operator", description: "Executa e acompanha as automações liberadas." },
    ]);
    if (caminho === "/papeis/funcionalidades") return json({ funcionalidades: [
      { chave: "fila", nome: "Fila", grupo: "Monitorar", href: "/fila", niveis: ["ver", "gerenciar"], o_que_gerenciar: null },
      { chave: "historico", nome: "Histórico", grupo: "Monitorar", href: "/historico", niveis: ["ver"], o_que_gerenciar: null },
      { chave: "auditoria", nome: "Auditoria", grupo: "Segurança", href: "/audit", niveis: ["ver"], o_que_gerenciar: null }] });
    if (caminho === "/papeis") return json({ pode_editar: true, papeis: [
      { id: 1, nome: "Administrador", slug: "admin", descricao: "Acesso total ao portal.", sistema: true, pessoas: 2,
        funcionalidades: { fila: "gerenciar", historico: "ver", auditoria: "ver" }, editavel: false, pode_apagar: false },
      { id: 2, nome: "Operador", slug: "operator", descricao: "Executa e acompanha as automações liberadas.", sistema: true, pessoas: 1,
        funcionalidades: { fila: "ver", historico: "ver" }, editavel: true, pode_apagar: false },
    ] });
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
    await expect(page.getByTestId("limpeza-notificacoes").getByText("7 dias")).toBeVisible();
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
  // liga um item que vinha fora: aparece no menu (lista única, no fim) e continua nas Configurações
  await areas.getByLabel("Mostrar Retenção no menu").check();
  await expect(menu.getByRole("link", { name: "Retenção" })).toBeVisible();
  await expect(menu.locator("[data-grupo]")).toHaveCount(0);
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

test("limpeza do sistema: padrão à mostra, fora da faixa recusa, encurtar avisa e salva", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/governance/retention");
  const secao = page.getByTestId("limpeza-do-sistema");
  const notificacoes = secao.getByTestId("limpeza-notificacoes");
  await expect(notificacoes.getByText("7 dias")).toBeVisible();
  await expect(notificacoes.getByText("42 apagados no total", { exact: false })).toBeVisible();
  await expect(secao.getByTestId("limpeza-sempre.auditoria").getByText("Guardado sempre")).toBeVisible();
  await expect(secao.getByRole("button", { name: "Mudar prazo de Auditoria" })).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/limpeza-do-sistema.png`, fullPage: true, animations: "disabled" });

  await secao.getByLabel("Buscar regra de limpeza").fill("medições");
  await expect(notificacoes).toHaveCount(0);
  await secao.getByLabel("Buscar regra de limpeza").fill("");

  await notificacoes.getByRole("button", { name: "Mudar prazo de Notificações" }).click();
  await page.getByLabel("Guardar por").fill("1");
  await expect(page.getByText("Use um número inteiro de 2 a 365.")).toBeVisible();
  await page.getByLabel("Guardar por").fill("3");
  await expect(page.getByRole("alert").getByText("apagado de vez", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Salvar e apagar o que passar do prazo" }).click();
  await expect(notificacoes.getByText("3 dias")).toBeVisible();
  await expect(notificacoes.getByText("Padrão: 7 dias")).toBeVisible();
  expect(pedidos.filter((p) => p.metodo === "PUT").map((p) => [p.caminho, p.corpo])).toEqual([
    ["/governance/limpeza/notificacoes", { dias: 3 }]]);
  expect(erros).toEqual([]);
});

test("limites: por grupo, o do .env só para consulta, mudar valida a faixa", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/governance/limits");
  const tela = page.getByTestId("limites-do-sistema");
  await expect(tela.getByRole("heading", { name: "Execuções" })).toBeVisible();
  await expect(tela.getByTestId("limite-execution.max_timeout_seconds").getByText("4 horas")).toBeVisible();
  const gateway = tela.getByTestId("limite-gateway.max_message_bytes");
  await expect(gateway.getByText("64 KB")).toBeVisible();
  await expect(gateway.getByText("Arquivo .env")).toBeVisible();
  await expect(gateway.getByRole("button")).toHaveCount(0);

  await tela.getByRole("button", { name: "Mudar Execuções ao mesmo tempo" }).click();
  await page.getByRole("spinbutton").fill("0");
  await expect(page.getByText("Use um número inteiro dentro da faixa.")).toBeVisible();
  await page.getByRole("spinbutton").fill("8");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(tela.getByTestId("limite-execution.max_concurrent").getByText("Padrão: 20")).toBeVisible();
  expect(pedidos.filter((p) => p.metodo === "PUT").map((p) => [p.caminho, p.corpo])).toEqual([
    ["/governance/limites/execution.max_concurrent", { valor: 8 }]]);
  expect(erros).toEqual([]);
});
