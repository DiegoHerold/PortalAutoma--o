import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Papéis globais (12/11/2026): a tabela funcionalidades × papéis. O admin muda cada célula (salva
 * na hora), cria, renomeia e apaga; quem não é admin só vê. O papel decide o menu e a tela de uma
 * funcionalidade fora do papel não abre pelo link. Sessão vencida leva ao login e volta.
 */

const TELAS = "../docs/papeis-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

const F = (chave: string, nome: string, grupo: string, href: string, gerencia = true, o_que = "") =>
  ({ chave, nome, grupo, href, niveis: gerencia ? ["ver", "gerenciar"] : ["ver"], o_que_gerenciar: o_que || null });
const FUNCIONALIDADES = [
  F("painel", "Painel", "Monitorar", "/dashboard", true, "Central de telas"), F("fila", "Fila", "Monitorar", "/fila"),
  F("historico", "Histórico", "Monitorar", "/historico", false), F("agendamentos", "Agendamentos", "Operação", "/schedules"),
  F("automacoes", "Automações", "Catálogo", "/automations"), F("auditoria", "Auditoria", "Segurança", "/audit", false),
  F("usuarios", "Usuários", "Pessoas e acesso", "/users"), F("papeis", "Papéis", "Pessoas e acesso", "/roles", false),
];

const PAPEIS = [
  { id: 1, nome: "Admin", slug: "admin", descricao: "Acesso total.", sistema: true, pessoas: 2, editavel: false, pode_apagar: false,
    funcionalidades: { painel: "gerenciar", fila: "gerenciar", historico: "ver", agendamentos: "gerenciar", automacoes: "gerenciar",
                       auditoria: "ver", usuarios: "gerenciar", papeis: "ver" } },
  { id: 3, nome: "Operator", slug: "operator", descricao: "Executa e acompanha.", sistema: true, pessoas: 1, editavel: true,
    pode_apagar: false, funcionalidades: { painel: "ver", fila: "gerenciar", historico: "ver", automacoes: "ver" } },
  { id: 7, nome: "Analista Fiscal", slug: "analista-fiscal", descricao: null, sistema: false, pessoas: 3, editavel: true,
    pode_apagar: true, funcionalidades: { painel: "ver", historico: "ver", auditoria: "ver" } },
];

async function preparar(page: Page, eu: Record<string, unknown>, extra?: (caminho: string) => unknown) {
  const pedidos: Pedido[] = [];
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    if (!window.sessionStorage.getItem("teste.iniciado")) {
      window.localStorage.setItem("portal_token", "token-de-teste");
      window.sessionStorage.setItem("teste.iniciado", "1");
    }
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
    const especial = extra?.(caminho);
    if (especial) return json((especial as { corpo: unknown }).corpo, (especial as { status: number }).status);
    if (caminho === "/auth/login") return json({ access_token: "token-novo", token_type: "bearer" });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", permissions: [], ...eu });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/papeis/funcionalidades") return json({ funcionalidades: FUNCIONALIDADES });
    if (caminho === "/papeis" && req.method() === "GET") return json({ papeis: PAPEIS, pode_editar: eu.role === "admin" });
    if (caminho === "/papeis") return json({ ...PAPEIS[2], id: 9, nome: corpo.nome }, 201);
    if (/^\/papeis\/\d+$/.test(caminho)) return json(req.method() === "DELETE" ? { id: 7, pessoas_movidas: 3 } : PAPEIS[1]);
    if (caminho === "/painel") return json({ gerado_em: new Date().toISOString(), central: false, execucoes: [], maquinas: [],
      fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, aguardando: { fila: [], perdidos: [] } });
    if (caminho === "/painel/recentes") return json({ automacoes: [], maquinas: [] });
    if (caminho === "/historico/resumo") return json({ dias: 7, total: 0, concluidas: 0, com_falha: 0, canceladas: 0, duracao_media_s: null });
    if (caminho === "/historico") return json({ execucoes: [], cursor: null });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("papéis: a tabela de funcionalidades; cada célula salva na hora", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page, { role: "admin", rbac_permissions: [] });
  await abrir(page, "/roles");
  const tabela = page.getByTestId("tabela-de-papeis");
  await expect(tabela.locator("th[data-papel]")).toHaveCount(3);
  await expect(tabela.locator("tr[data-funcionalidade]")).toHaveCount(8);
  await expect(tabela.locator("tr[data-funcionalidade='usuarios'] td").nth(1)).toHaveText("Tudo");  // Admin travado
  // Auditoria só se vê: não oferece "Gerenciar".
  await expect(tabela.getByLabel("Operator: Auditoria").locator("option")).toHaveText(["—", "Ver"]);
  await page.screenshot({ path: `${TELAS}/papeis-tabela-1920.png`, fullPage: true, animations: "disabled" });

  await tabela.getByLabel("Operator: Agendamentos").selectOption("gerenciar");
  await expect.poll(() => pedidos.find((p) => p.metodo === "PUT" && p.caminho === "/papeis/3")?.corpo).toEqual({
    funcionalidades: { painel: "ver", fila: "gerenciar", historico: "ver", automacoes: "ver", agendamentos: "gerenciar" } });
  await tabela.getByLabel("Analista Fiscal: Auditoria").selectOption("");
  await expect.poll(() => pedidos.find((p) => p.metodo === "PUT" && p.caminho === "/papeis/7")?.corpo).toEqual({
    funcionalidades: { painel: "ver", historico: "ver", auditoria: null } });

  await page.getByRole("button", { name: "Novo papel" }).click();
  const janela = page.getByRole("dialog");
  await janela.getByLabel("Nome do papel").fill("Conferência");
  await janela.getByLabel("Baseado em").selectOption("7");
  await janela.getByRole("button", { name: "Criar papel" }).click();
  await expect.poll(() => pedidos.find((p) => p.metodo === "POST" && p.caminho === "/papeis")?.corpo)
    .toEqual({ nome: "Conferência", descricao: "", baseado_em: 7 });

  await tabela.locator("th[data-papel='analista-fiscal']").getByRole("button", { name: "Apagar Analista Fiscal" }).click();
  const apagar = page.getByRole("dialog");
  await expect(apagar.getByRole("button", { name: "Apagar papel" })).toBeDisabled();
  await apagar.getByLabel("Papel substituto").selectOption("3");
  await apagar.getByRole("button", { name: "Apagar papel" }).click();
  await expect.poll(() => pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/papeis/7?substituto=3")).toBe(true);
  expect(erros).toEqual([]);
});

test("papéis: quem não é admin vê a tabela sem poder mudar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { role: "manager", rbac_permissions: ["papeis.ver", "painel.ver"] });
  await abrir(page, "/roles");
  await expect(page.getByTestId("tabela-de-papeis").locator("tr[data-funcionalidade]")).toHaveCount(8);
  await expect(page.getByTestId("tabela-de-papeis").locator("select")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Novo papel" })).toHaveCount(0);
  await expect(page.getByText("Só administradores mudam os papéis.")).toBeVisible();
  expect(erros).toEqual([]);
});

test("o papel decide o menu; tela fora do papel não abre pelo link; sem Painel vai para a primeira tela", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { role: "analista", rbac_permissions: ["historico.ver", "auditoria.ver", "audit.read"] });
  await abrir(page, "/dashboard");
  await expect(page).toHaveURL(/\/historico$/);  // não tem o Painel: vai para a primeira tela que tem
  const menu = page.getByRole("navigation", { name: "Menu" });
  await expect(menu.locator("[data-item-menu='/historico']")).toBeVisible();
  await expect(menu.locator("[data-item-menu='/dashboard']")).toHaveCount(0);
  await expect(menu.locator("[data-item-menu='/fila']")).toHaveCount(0);
  await abrir(page, "/fila");
  await expect(page.getByTestId("sem-acesso")).toContainText("Sem acesso a Fila");
  await page.screenshot({ path: `${TELAS}/sem-acesso.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("sessão vencida: avisa, leva ao login e volta para a mesma tela", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let vencida = false;
  const { erros } = await preparar(page, { role: "admin", rbac_permissions: [] }, (caminho) =>
    vencida && caminho.startsWith("/papeis") ? { status: 401, corpo: { detail: "Could not validate credentials." } } : null);
  await abrir(page, "/roles");
  await expect(page.getByTestId("tabela-de-papeis")).toBeVisible();
  vencida = true;  // passou a hora do token
  await page.getByTestId("tabela-de-papeis").getByLabel("Operator: Fila").selectOption("ver");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByTestId("sessao-expirada")).toContainText("Sua sessão expirou");
  vencida = false;
  await page.getByRole("button", { name: /Entrar no portal/ }).click();
  await expect(page).toHaveURL(/\/roles$/);  // voltou para onde estava
  expect(erros).toEqual([]);
});
