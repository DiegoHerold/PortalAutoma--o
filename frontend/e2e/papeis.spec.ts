import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Papéis globais (12/11/2026): o admin cria, muda as abas e apaga (com substituto); quem não é
 * admin só vê. As abas do papel decidem o menu e a tela de uma aba desligada não abre pelo link.
 */

const TELAS = "../docs/papeis-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

const ABAS = [
  { chave: "/fila", rotulo: "Fila", grupo: "Monitorar" }, { chave: "/maquinas", rotulo: "Máquinas", grupo: "Monitorar" },
  { chave: "/historico", rotulo: "Histórico", grupo: "Monitorar" }, { chave: "/executions", rotulo: "Execuções", grupo: "Operação" },
  { chave: "/schedules", rotulo: "Agendamentos", grupo: "Operação" }, { chave: "/automations", rotulo: "Automações", grupo: "Catálogo" },
  { chave: "/audit", rotulo: "Auditoria", grupo: "Segurança" }, { chave: "/users", rotulo: "Usuários", grupo: "Pessoas e acesso" },
];

const PAPEIS = [
  { id: 1, nome: "Admin", slug: "admin", descricao: "Acesso total.", sistema: true, pessoas: 2, abas: ABAS.map((a) => a.chave),
    pode_mudar_abas: false, pode_apagar: false },
  { id: 3, nome: "Operator", slug: "operator", descricao: "Executa e acompanha.", sistema: true, pessoas: 1,
    abas: ["/fila", "/maquinas", "/historico", "/executions", "/automations"], pode_mudar_abas: true, pode_apagar: false },
  { id: 4, nome: "Viewer", slug: "viewer", descricao: "Só vê.", sistema: true, pessoas: 0, abas: ["/historico"],
    pode_mudar_abas: true, pode_apagar: false },
  { id: 7, nome: "Analista Fiscal", slug: "analista-fiscal", descricao: null, sistema: false, pessoas: 3,
    abas: ["/historico", "/audit"], pode_mudar_abas: true, pode_apagar: true },
];

async function preparar(page: Page, eu: Record<string, unknown>) {
  const pedidos: Pedido[] = [];
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", "light");
  });
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", permissions: [], ...eu });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/papeis/abas") return json({ abas: ABAS });
    if (caminho === "/papeis" && req.method() === "GET") return json({ papeis: PAPEIS, pode_editar: eu.role === "admin" });
    if (caminho === "/papeis") return json({ ...PAPEIS[3], id: 9, nome: corpo.nome, abas: corpo.abas }, 201);
    if (/^\/papeis\/\d+$/.test(caminho)) return json(req.method() === "DELETE" ? { id: 7, pessoas_movidas: 3 } : PAPEIS[2]);
    if (caminho === "/painel") return json({ gerado_em: new Date().toISOString(), central: false, execucoes: [], maquinas: [],
      fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, aguardando: { fila: [], perdidos: [] } });
    if (caminho === "/painel/recentes") return json({ automacoes: [], maquinas: [] });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("papéis: o admin cria com as abas, edita e apaga escolhendo o substituto", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page, { role: "admin", rbac_permissions: [] });
  await abrir(page, "/roles");
  const tela = page.getByTestId("papeis");
  await expect(tela.locator("[data-papel]")).toHaveCount(4);
  await expect(tela.locator("[data-papel='admin']")).toContainText("Todas as abas");
  await expect(tela.locator("[data-papel='admin']").getByRole("button", { name: /Apagar/ })).toHaveCount(0);
  await expect(tela.locator("[data-papel='analista-fiscal']").getByTestId("abas-do-papel")).toContainText("Auditoria");
  await page.screenshot({ path: `${TELAS}/papeis-1920.png`, fullPage: true, animations: "disabled" });

  // Novo papel baseado no Viewer: as abas dele já vêm marcadas.
  await page.getByRole("button", { name: "Novo papel" }).click();
  const janela = page.getByRole("dialog");
  await janela.getByLabel("Nome do papel").fill("Conferência");
  await janela.getByLabel("Baseado em").selectOption("4");
  await expect(janela.getByRole("checkbox", { name: "Histórico" })).toBeChecked();
  await janela.getByRole("checkbox", { name: "Auditoria" }).check();
  await page.screenshot({ path: `${TELAS}/papel-novo.png`, animations: "disabled" });
  await janela.getByRole("button", { name: "Criar papel" }).click();
  await expect.poll(() => pedidos.find((p) => p.metodo === "POST" && p.caminho === "/papeis")?.corpo)
    .toEqual({ nome: "Conferência", descricao: "", abas: ["/historico", "/audit"], baseado_em: 4 });

  // Editar as abas do Operator: tirar a Fila.
  await tela.locator("[data-papel='operator']").getByRole("button", { name: "Editar Operator" }).click();
  await page.getByRole("dialog").getByRole("checkbox", { name: "Fila" }).uncheck();
  await page.getByRole("dialog").getByRole("button", { name: "Salvar" }).click();
  await expect.poll(() => (pedidos.find((p) => p.metodo === "PUT" && p.caminho === "/papeis/3")?.corpo as { abas: string[] })?.abas)
    .toEqual(["/maquinas", "/historico", "/executions", "/automations"]);

  // O Admin não muda de abas.
  await tela.locator("[data-papel='admin']").getByRole("button", { name: "Editar Admin" }).click();
  await expect(page.getByRole("dialog")).toContainText("O papel Admin vê todas as abas.");
  await expect(page.getByRole("dialog").getByRole("checkbox")).toHaveCount(0);
  await page.getByRole("dialog").getByRole("button", { name: "Voltar" }).click();

  // Apagar com pessoas pede o substituto.
  await tela.locator("[data-papel='analista-fiscal']").getByRole("button", { name: "Apagar Analista Fiscal" }).click();
  const apagar = page.getByRole("dialog");
  await expect(apagar).toContainText("3 pessoa(s) têm este papel");
  await expect(apagar.getByRole("button", { name: "Apagar papel" })).toBeDisabled();
  await apagar.getByLabel("Papel substituto").selectOption("4");
  await page.screenshot({ path: `${TELAS}/papel-apagar.png`, animations: "disabled" });
  await apagar.getByRole("button", { name: "Apagar papel" }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/papeis/7?substituto=4")).toBe(true);
  expect(erros).toEqual([]);
});

test("papéis: quem não é admin só vê, sem botões", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { role: "manager", rbac_permissions: ["admin.roles"], abas: null });
  await abrir(page, "/roles");
  await expect(page.getByTestId("papeis").locator("[data-papel]")).toHaveCount(4);
  await expect(page.getByText("Só administradores mudam os papéis.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Novo papel" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Editar / })).toHaveCount(0);
  expect(erros).toEqual([]);
});

test("abas do papel: o menu mostra só as ligadas e a tela desligada não abre pelo link", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { role: "operator", rbac_permissions: ["execution.read", "automation.read"],
                                           abas: ["/historico", "/automations"] });
  await abrir(page, "/dashboard");
  const menu = page.getByRole("navigation", { name: "Menu" });
  await expect(menu.locator("[data-item-menu='/historico']")).toBeVisible();
  await expect(menu.locator("[data-item-menu='/fila']")).toHaveCount(0);  // tem a permissão, mas a aba está desligada
  await expect(menu.locator("[data-item-menu='/dashboard']")).toBeVisible();  // o Painel sempre
  await abrir(page, "/fila");
  await expect(page.getByTestId("sem-acesso")).toContainText("Sem acesso a Fila");
  await page.screenshot({ path: `${TELAS}/sem-acesso.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});
