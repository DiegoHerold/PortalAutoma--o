import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Apagar uma máquina (com o aviso do que depende dela), os membros e as permissões de um time e
 * os times no cadastro do usuário. A API é simulada só aqui.
 */

const TELAS = "../docs/times-e-maquinas-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

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
  let maquinas = [
    { id: "mch_agt_worker_1", nome: "Local Simulated Worker", status: "ativa" },
    { id: "mch_10", nome: "MAQ10", status: "ativa" },
    { id: "mch_194", nome: "MAQ194", status: "ativa" },
  ];
  let membros = [{ id: 2, nome: "Ana de Teste", email: "ana@teste.invalid", ativo: true }];
  let categorias = [{ category_id: 1, categoria: "Folha", can_view: true, can_execute: false }];
  let automacoesDoTime = [{ automation_id: 7, automacao: "Integração Contábil · Folha", acoes: ["ver_execucoes"] }];
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "admin@teste.invalid", name: "Admin de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/painel/linha-do-tempo") return json({ inicio: em(-6 * 3600), fim: em(6 * 3600), agora: em(0), agora_posicao: 50,
      marcas: [], maquinas: maquinas.map((m) => ({ maquina_id: m.id, nome: m.nome, blocos: [] })) });
    if (caminho === "/instancias-diretas") return json({ instancias: [] });
    if (caminho === "/maquinas") return json({ maquinas });
    const vinc = caminho.match(/^\/maquinas\/(\w+)\/vinculos$/);
    if (vinc) {
      const m = maquinas.find((x) => x.id === vinc[1])!;
      if (m.id === "mch_194") return json({ maquina: { id: m.id, nome: m.nome }, automacoes: [
        { instancia_id: "dri_1", automation_id: 7, automacao: "Integração Contábil · Folha", situacao: "aprovada" }], agents: [], fila: 2, rodando: 0 });
      if (m.id === "mch_10") return json({ maquina: { id: m.id, nome: m.nome }, automacoes: [], agents: [], fila: 0, rodando: 1 });
      return json({ maquina: { id: m.id, nome: m.nome }, automacoes: [], agents: [], fila: 0, rodando: 0 });
    }
    const apagar = caminho.match(/^\/maquinas\/(\w+)$/);
    if (apagar && req.method() === "DELETE") {
      maquinas = maquinas.filter((m) => m.id !== apagar[1]);
      return json({ id: apagar[1], nome: "x", automacoes_sem_maquina: 0, agents_sem_maquina: 0, jobs_liberados: 0 });
    }
    if (caminho === "/automations") return json([
      { id: 7, name: "Integração Contábil · Folha", slug: "ic", category_id: 1, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true },
      { id: 9, name: "Conferência de guias", slug: "cg", category_id: 2, executor_type: "direto", default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true }]);
    if (caminho === "/organizations") return json([{ id: 1, key: "biason", name: "Biason", status: "active", created_at: em(-86400), updated_at: em(-86400) }]);
    if (caminho === "/teams") return json([
      { id: 4, organization_id: 1, key: "folha", name: "Folha", status: "active", created_at: em(-86400), updated_at: em(-86400) },
      { id: 5, organization_id: 1, key: "fiscal", name: "Fiscal", status: "active", created_at: em(-86400), updated_at: em(-86400) }]);
    if (caminho === "/teams/4/detalhes") return json({ membros, categorias, automacoes: automacoesDoTime,
      acoes_possiveis: ["ver_execucoes", "ver_telas_e_logs", "editar_itens", "executar", "controlar"] });
    if (caminho === "/teams/4/membros" && req.method() === "POST") {
      membros = [...membros, { id: 3, nome: "Bruno de Teste", email: "bruno@teste.invalid", ativo: true }];
      return json({ membros });
    }
    if (caminho === "/teams/4/membros/2" && req.method() === "DELETE") {
      membros = membros.filter((m) => m.id !== 2);
      return json({ membros });
    }
    if (caminho === "/teams/4/categorias") {
      categorias = (corpo as { categorias: typeof categorias }).categorias.map((c) => ({ ...c, categoria: c.category_id === 1 ? "Folha" : "Fiscal" }));
      return json({ categorias });
    }
    const acesso = caminho.match(/^\/automations\/(\d+)\/acessos$/);
    if (acesso && req.method() === "PUT") {
      const id = Number(acesso[1]);
      const acoes = (corpo as { acoes: string[] }).acoes;
      automacoesDoTime = acoes.length
        ? [...automacoesDoTime.filter((a) => a.automation_id !== id), { automation_id: id, automacao: id === 9 ? "Conferência de guias" : "Integração Contábil · Folha", acoes }]
        : automacoesDoTime.filter((a) => a.automation_id !== id);
      return json({ concessao: null });
    }
    if (caminho === "/categories") return json([{ id: 1, name: "Folha", slug: "folha" }, { id: 2, name: "Fiscal", slug: "fiscal" }]);
    if (caminho === "/roles") return json([{ id: 3, name: "Operador", slug: "operator", permissions: [] }]);
    if (caminho === "/users") {
      if (req.method() === "POST") return json({ id: 3, name: "Bruno de Teste", email: "bruno@teste.invalid", is_active: true,
        role: { id: 3, name: "Operador", slug: "operator", permissions: [] }, category_permissions: [] }, 201);
      return json([
        { id: 2, name: "Ana de Teste", email: "ana@teste.invalid", is_active: true, role: { id: 3, name: "Operador", slug: "operator", permissions: [] }, category_permissions: [] },
        { id: 3, name: "Bruno de Teste", email: "bruno@teste.invalid", is_active: true, role: { id: 3, name: "Operador", slug: "operator", permissions: [] }, category_permissions: [] }]);
    }
    if (caminho === "/users/2" && req.method() === "PUT") return json({ id: 2, name: "Ana de Teste", email: "ana@teste.invalid", is_active: true,
      role: { id: 3, name: "Operador", slug: "operator", permissions: [] }, category_permissions: [] });
    if (caminho === "/acesso/pessoas") return json({ times: { "2": [{ id: 4, nome: "Folha", ativo: true }] } });
    if (caminho === "/acesso/pessoas/2") return json({
      pessoa: { id: 2, nome: "Ana de Teste", email: "ana@teste.invalid" },
      papel: { id: 3, nome: "Operador", slug: "operator", telas: [
        { chave: "painel", nome: "Painel", grupo: "Monitorar", nivel: "ver" }, { chave: "fila", nome: "Fila", grupo: "Monitorar", nivel: "gerenciar" },
        { chave: "historico", nome: "Histórico", grupo: "Monitorar", nivel: "ver" }] },
      times: [{ id: 4, nome: "Folha", ativo: true, categorias: [{ categoria: "Folha", ver: true, executar: true, editar: false, publicar: false }],
                automacoes: [{ automation_id: 7, automacao: "Integração Contábil · Folha", acoes: ["ver_telas_e_logs"] }] }],
      excecoes: [{ automation_id: 9, automacao: "Conferência de guias", acoes: ["controlar"] }], permissoes_soltas: false });
    if (caminho === "/users/2/times" && req.method() === "GET") return json({ times: [{ id: 4, nome: "Folha", situacao: "active" }] });
    if (/^\/users\/\d+\/times$/.test(caminho)) return json({ times: [] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("máquina: apagar avisa o que depende dela e pede confirmação; sem vínculo apaga direto; rodando não apaga", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/maquinas");
  await page.getByRole("button", { name: "Gerenciar" }).click();
  const lista = page.getByTestId("maquinas-cadastradas");
  await expect(lista.getByRole("listitem")).toHaveCount(3);

  await lista.getByRole("button", { name: "Apagar MAQ194" }).click();
  const janela = page.getByTestId("apagar-maquina");
  await expect(janela.getByText("Integração Contábil · Folha")).toBeVisible();
  await expect(janela.getByText("2 pedido(s)", { exact: false })).toBeVisible();
  await expect(janela.getByText("sem máquina", { exact: false })).toBeVisible();
  await page.screenshot({ path: `${TELAS}/apagar-maquina-com-vinculos.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Apagar mesmo assim" }).click();
  await expect(lista.getByRole("listitem")).toHaveCount(2);
  expect(pedidos.filter((p) => p.metodo === "DELETE").map((p) => p.caminho)).toEqual(["/maquinas/mch_194?confirmar=true"]);

  await lista.getByRole("button", { name: "Apagar MAQ10" }).click();
  await expect(page.getByTestId("apagar-maquina").getByText("1 execução(ões) rodando", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Apagar", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Cancelar" }).click();

  await lista.getByRole("button", { name: "Apagar Local Simulated Worker" }).click();
  await expect(page.getByTestId("apagar-maquina").getByText("Nenhuma automação", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Apagar", exact: true }).click();
  await expect(lista.getByRole("listitem")).toHaveCount(1);
  expect(pedidos.filter((p) => p.metodo === "DELETE").map((p) => p.caminho).at(-1)).toBe("/maquinas/mch_agt_worker_1");
  await expect(page.getByTestId("linha-do-tempo").getByText("Local Simulated Worker")).toHaveCount(0);  // some da linha do tempo
  await page.screenshot({ path: `${TELAS}/maquinas-depois.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("time: membros, permissões por categoria e por automação", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/teams");
  await page.getByRole("row", { name: /Folha/ }).getByRole("button", { name: "Membros e permissões" }).click();
  const painel = page.getByTestId("time-detalhes");
  await expect(painel.getByText("Ana de Teste")).toBeVisible();

  await painel.getByLabel("Pessoa para adicionar").selectOption("3");
  await painel.getByRole("button", { name: "Adicionar" }).click();
  await expect(painel.getByText("Bruno de Teste")).toBeVisible();
  await painel.getByRole("button", { name: "Tirar Ana de Teste do time" }).click();
  await expect(painel.getByRole("button", { name: "Tirar Ana de Teste do time" })).toHaveCount(0);  // volta a ser candidata

  await painel.getByLabel("Executar Fiscal").check();
  await expect(painel.getByLabel("Ver Fiscal")).toBeChecked();  // quem executa vê
  await painel.getByLabel("Editar Folha").check();  // editar = criar, editar e apagar o cadastro
  await painel.getByTestId("time-categorias").locator("..").getByRole("button", { name: "Salvar" }).click();
  const sem = { can_create: false, can_edit: false, can_delete: false, can_approve: false };
  await expect.poll(() => pedidos.find((p) => p.caminho === "/teams/4/categorias")?.corpo).toEqual({ categorias: [
    { category_id: 1, can_view: true, can_execute: false, can_create: true, can_edit: true, can_delete: true, can_approve: false },
    { category_id: 2, can_view: true, can_execute: true, ...sem }] });

  await painel.getByLabel("Ver telas e logs em Integração Contábil · Folha").check();
  await expect.poll(() => pedidos.filter((p) => p.caminho === "/automations/7/acessos").at(-1)?.corpo)
    .toEqual({ team_id: 4, acoes: ["ver_execucoes", "ver_telas_e_logs"] });
  await painel.getByLabel("Automação para dar acesso").selectOption("9");
  await painel.getByRole("button", { name: "Dar acesso" }).click();
  await expect(painel.getByTestId("time-automacoes").getByText("Conferência de guias")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/time-membros-e-permissoes.png`, fullPage: true, animations: "disabled" });
  expect(pedidos.filter((p) => p.caminho === "/automations/9/acessos").map((p) => p.corpo)).toEqual([{ team_id: 4, acoes: ["ver_execucoes"] }]);
  expect(erros).toEqual([]);
});

test("usuário: a lista mostra os times e o que a pessoa acessa (telas, automações e exceções)", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/users");
  const linhas = page.getByTestId("times-da-pessoa");
  await expect(linhas.nth(0)).toContainText("Folha");
  await expect(linhas.nth(1)).toContainText("nenhum");
  await page.getByRole("button", { name: "O que Ana de Teste acessa" }).click();
  const resumo = page.getByTestId("resumo-de-acesso");
  await expect(resumo).toContainText("Pelo papel Operador");
  await expect(resumo).toContainText("Vê e altera: Fila");
  await expect(resumo).toContainText("Só vê: Painel, Histórico");
  await expect(resumo).toContainText("Folha: ver, executar");
  await expect(resumo).toContainText("Integração Contábil · Folha: ver telas e logs");
  await expect(resumo).toContainText("Conferência de guias: parar e retomar");
  // O editor antigo de permissões soltas saiu.
  await expect(page.getByText("Salvar permissões")).toHaveCount(0);
  expect(pedidos.some((p) => p.caminho.endsWith("/permissions"))).toBe(false);
  await page.screenshot({ path: `${TELAS}/usuario-o-que-acessa.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("usuário: escolher os times ao criar e ao editar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/users");

  await page.getByRole("button", { name: "Editar usuário" }).first().click();
  const times = page.getByTestId("times-do-usuario");
  await expect(times.getByLabel("Time Folha")).toBeChecked();  // o que ela já tem
  await times.getByLabel("Time Fiscal").check();
  await page.screenshot({ path: `${TELAS}/usuario-times.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect.poll(() => pedidos.find((p) => p.metodo === "PUT" && p.caminho === "/users/2/times")?.corpo).toEqual({ times: [4, 5] });

  await page.getByRole("button", { name: /Novo usuário|Novo/ }).first().click();
  await page.getByLabel("Nome").fill("Bruno de Teste");
  await page.getByLabel("E-mail").fill("bruno@teste.invalid");
  await expect(page.getByText("A pessoa recebe um e-mail para criar a própria senha")).toBeVisible();
  await page.getByLabel("Papel").selectOption("3");
  await page.getByTestId("times-do-usuario").getByLabel("Time Fiscal").check();
  await page.getByRole("button", { name: "Criar" }).click();
  await expect.poll(() => pedidos.find((p) => p.metodo === "PUT" && p.caminho === "/users/3/times")?.corpo).toEqual({ times: [5] });
  // sem senha no cadastro: a pessoa cria a dela pelo convite
  expect(pedidos.find((p) => p.metodo === "POST" && p.caminho === "/users")?.corpo).not.toHaveProperty("password");
  expect(erros).toEqual([]);
});
