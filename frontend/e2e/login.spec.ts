import { mkdirSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Login com código (13/11/2026): senha, depois o código de 6 dígitos que chega por e-mail; "Confiar
 * neste navegador" guarda o dispositivo e, na volta, a senha basta. Esqueci a senha e criar a senha
 * pelo link do e-mail (o token vem no fragmento #t=, não vai ao servidor na URL).
 */

const TELAS = "../docs/login-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: Record<string, unknown> | null };

async function preparar(page: Page, { linkValido = true, tema = "light" } = {}) {
  const erros: string[] = [];
  const pedidos: Pedido[] = [];
  page.on("console", (m) => m.type() === "error" && !/40[0-9]|41[0-9]|422/.test(m.text()) && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript((t) => {
    try { window.localStorage.setItem("portal_theme", t); } catch { /* sem armazenamento */ }
  }, tema);
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  let tentativas = 5;
  let confiaveis = [{ id: "dsp_1", desde: new Date(Date.now() - 86_400_000).toISOString(),
    vale_ate: new Date(Date.now() + 29 * 86_400_000).toISOString(), navegador: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0" }];
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const r: Request = route.request();
    const caminho = new URL(r.url()).pathname.replace("/api/v1", "");
    const corpo = r.postData() ? (JSON.parse(r.postData()!) as Record<string, unknown>) : null;
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (r.method() !== "GET") pedidos.push({ metodo: r.method(), caminho, corpo });
    const vale = new Date(Date.now() + 600_000).toISOString();
    if (caminho === "/auth/login") {
      if (corpo?.password !== "Senha-certa-1") return json({ erro: "E-mail ou senha incorretos." }, 401);
      if (corpo?.dispositivo === "disp-confiavel") return json({ access_token: "token-novo", token_type: "bearer" });
      tentativas = 5;
      return json({ precisa_codigo: true, desafio: "des_1", email: "an***@biason.net", codigo_vale_ate: vale, tentativas });
    }
    if (caminho === "/auth/codigo") {
      if (corpo?.codigo === "123456") {
        return json({ access_token: "token-novo", token_type: "bearer", ...(corpo.confiar ? { dispositivo: "disp-confiavel" } : {}) });
      }
      tentativas -= 1;
      if (tentativas <= 0) return json({ erro: "Errou o código 5 vezes. Entre de novo com a senha.", restantes: 0, voltar_ao_login: true }, 401);
      return json({ erro: `Código não confere. Restam ${tentativas} tentativas.`, restantes: tentativas, voltar_ao_login: false }, 401);
    }
    if (caminho === "/auth/codigo/reenviar") return json({ email: "an***@biason.net", codigo_vale_ate: vale, tentativas: 5 });
    if (caminho === "/auth/esqueci") return json({ mensagem: "Se o e-mail tiver conta no Portal, mandamos um link para criar uma senha nova." });
    if (caminho === "/auth/senha/ver") {
      if (!linkValido || corpo?.token !== "tok-do-email") return json({ erro: "Este link já foi usado ou venceu. Peça outro." }, 410);
      return json({ tipo: "convite", email: "ana.lima@biason.net", nome: "Ana Lima", vale_ate: vale });
    }
    if (caminho === "/auth/senha") return json({ mensagem: "Senha salva." });
    if (caminho === "/auth/trocar-senha") {
      if (corpo?.atual !== "Senha-certa-1") return json({ erro: "A senha atual não confere." }, 422);
      confiaveis = [];
      return json({ mensagem: "Senha trocada." });
    }
    if (caminho === "/auth/navegadores") {
      if (r.method() === "DELETE") { const n = confiaveis.length; confiaveis = []; return json({ esquecidos: n }); }
      return json({ navegadores: confiaveis });
    }
    if (caminho === "/auth/me") {
      if (!r.headers()["authorization"]) return json({ detail: "Not authenticated" }, 401);
      return json({ id: 1, email: "ana.lima@biason.net", name: "Ana Lima", role: "admin", permissions: [], rbac_permissions: [] });
    }
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { erros, pedidos };
}

async function senha(page: Page, valor = "Senha-certa-1") {
  await page.getByLabel("E-mail").fill("ana.lima@biason.net");
  await page.getByLabel("Senha", { exact: true }).fill(valor);
  await page.getByRole("button", { name: /Entrar no portal/ }).click();
}

test("senha, código e navegador confiável: na volta, só a senha", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/settings#conta");  // sem login: vai ao login e volta para cá depois
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByTestId("passo-da-senha")).toBeVisible();
  await expect(page.getByLabel("E-mail")).toHaveValue("");  // nada pré-preenchido
  await page.screenshot({ path: `${TELAS}/login-1440.png`, animations: "disabled" });

  await senha(page, "errada");
  await expect(page.getByTestId("erro-do-login")).toContainText("E-mail ou senha incorretos.");

  await senha(page);
  const passo = page.getByTestId("passo-do-codigo");
  await expect(passo).toContainText("an***@biason.net");
  await expect(passo.getByRole("button", { name: /Reenviar código em \d+s/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /^Entrar/ })).toBeDisabled();  // falta o código
  await page.getByLabel("Código").fill("000000");
  await page.getByRole("button", { name: /^Entrar/ }).click();
  await expect(page.getByTestId("erro-do-login")).toContainText("Restam 4 tentativas");
  await expect(page.getByLabel("Código")).toHaveValue("");

  await page.getByLabel("Código").fill("123 456");  // colado com espaço: fica só os dígitos
  await expect(page.getByLabel("Código")).toHaveValue("123456");
  await page.getByLabel(/Confiar neste navegador por 30 dias/).check();
  await page.screenshot({ path: `${TELAS}/codigo-1440.png`, animations: "disabled" });
  await page.getByRole("button", { name: /^Entrar/ }).click();
  await expect(page).toHaveURL(/\/settings#conta$/);
  expect(pedidos.find((p) => p.caminho === "/auth/codigo" && p.corpo?.codigo === "123456")?.corpo).toMatchObject({ desafio: "des_1", confiar: true });
  const guardado = await page.evaluate(() => window.localStorage.getItem("portal_dispositivos"));
  expect(JSON.parse(guardado ?? "{}")).toEqual({ "ana.lima@biason.net": "disp-confiavel" });

  // sai; abre um link de dentro do Portal; entra de novo: o navegador confiável manda o dispositivo,
  // não pede código e volta para onde a pessoa ia
  await page.evaluate(() => window.localStorage.removeItem("portal_token"));
  await page.goto("about:blank");
  await page.goto("/settings#conta");
  await expect(page).toHaveURL(/\/login/);
  await senha(page);
  await expect(page).toHaveURL(/\/settings#conta$/);
  await expect(page.getByTestId("senha-e-acesso")).toBeVisible();
  expect(pedidos.filter((p) => p.caminho === "/auth/login").at(-1)?.corpo).toMatchObject({ dispositivo: "disp-confiavel" });
  expect(pedidos.filter((p) => p.caminho === "/auth/codigo")).toHaveLength(2);
  expect(erros).toEqual([]);
});

test("Configurações › Sua conta: trocar a senha e esquecer os navegadores", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.addInitScript(() => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_dispositivos", JSON.stringify({ "ana.lima@biason.net": "disp-confiavel" }));
  });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/settings#conta");
  const secao = page.getByTestId("senha-e-acesso");
  await expect(secao.getByTestId("navegadores")).toContainText("Edge no Windows");
  const trocar = secao.getByRole("button", { name: "Trocar a senha" });
  await expect(trocar).toBeDisabled();
  await secao.getByLabel("Senha atual").fill("Senha-errada-1");
  await secao.getByLabel("Senha nova").fill("Fiscal-Planet-2026");
  await secao.getByLabel("Repita a senha").fill("Fiscal-Planet-2026");
  await trocar.click();
  await expect(secao.getByRole("alert")).toContainText("A senha atual não confere.");
  await secao.getByLabel("Senha atual").fill("Senha-certa-1");
  await page.screenshot({ path: `${TELAS}/configuracoes-senha-1440.png`, fullPage: true, animations: "disabled" });
  await trocar.click();
  await expect(page.getByText("Senha trocada")).toBeVisible();
  expect(pedidos.filter((p) => p.caminho === "/auth/trocar-senha").at(-1)?.corpo).toEqual({ atual: "Senha-certa-1", nova: "Fiscal-Planet-2026" });
  await expect(secao.getByLabel("Senha atual")).toHaveValue("");
  // trocar a senha esquece os navegadores confiáveis (aqui e no Portal)
  expect(await page.evaluate(() => window.localStorage.getItem("portal_dispositivos"))).toBe("{}");
  await expect(secao).toContainText("Nenhum agora: todo login pede o código.");
  expect(erros).toEqual([]);
});

test("Configurações › Sua conta: esquecer todos os navegadores", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.addInitScript(() => window.localStorage.setItem("portal_token", "token-de-teste"));
  const { erros, pedidos } = await preparar(page);
  await page.goto("/settings#conta");
  const secao = page.getByTestId("senha-e-acesso");
  await secao.getByRole("button", { name: "Esquecer todos" }).click();
  await expect(page.getByText("Navegadores esquecidos")).toBeVisible();
  expect(pedidos.some((p) => p.metodo === "DELETE" && p.caminho === "/auth/navegadores")).toBe(true);
  await expect(secao).toContainText("Nenhum agora");
  expect(erros).toEqual([]);
});

test("código: reenviar depois da espera e voltar ao login após 5 erros", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.clock.install();
  const { erros, pedidos } = await preparar(page);
  await page.goto("/login");
  await senha(page);
  const reenviar = page.getByTestId("passo-do-codigo").getByRole("button", { name: /Reenviar código/ });
  await expect(reenviar).toBeDisabled();
  await page.clock.runFor(31_000);
  await expect(reenviar).toHaveText("Reenviar código");
  await reenviar.click();
  await expect(page.getByText("Mandamos um código novo. O anterior não vale mais.")).toBeVisible();
  expect(pedidos.filter((p) => p.caminho === "/auth/codigo/reenviar")).toHaveLength(1);

  for (let i = 0; i < 5; i += 1) {
    await page.getByLabel("Código").fill("000000");
    await page.getByRole("button", { name: /^Entrar/ }).click();
    if (i < 4) await expect(page.getByTestId("erro-do-login")).toContainText(`Restam ${4 - i}`);
  }
  await expect(page.getByTestId("passo-da-senha")).toBeVisible();
  await expect(page.getByText("Errou o código 5 vezes. Entre de novo com a senha.")).toBeVisible();
  await expect(page.getByLabel("Senha", { exact: true })).toHaveValue("");
  expect(erros).toEqual([]);
});

test("esqueci a senha: mesma resposta para qualquer e-mail", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("ana.lima@biason.net");
  await page.getByRole("link", { name: "Esqueci a senha" }).click();
  await expect(page).toHaveURL(/\/esqueci-senha\?email=ana\.lima%40biason\.net/);
  await expect(page.getByLabel("E-mail da sua conta")).toHaveValue("ana.lima@biason.net");
  await page.screenshot({ path: `${TELAS}/esqueci-1440.png`, animations: "disabled" });
  await page.getByRole("button", { name: "Mandar o link" }).click();
  await expect(page.getByTestId("link-pedido")).toContainText("mandamos um link para criar uma senha nova. O link vale 1 hora.");
  expect(pedidos.find((p) => p.caminho === "/auth/esqueci")?.corpo).toEqual({ email: "ana.lima@biason.net" });
  await page.getByRole("link", { name: "Voltar ao login" }).click();
  await expect(page).toHaveURL(/\/login/);
  expect(erros).toEqual([]);
});

test("criar a senha pelo convite: regras, confirmação e o token sai da barra", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros, pedidos } = await preparar(page);
  await page.goto("/redefinir-senha#t=tok-do-email");
  await expect(page.getByRole("heading", { name: "Crie sua senha" })).toBeVisible();
  await expect(page.getByText("Olá, Ana Lima.")).toBeVisible();
  const salvar = page.getByRole("button", { name: "Salvar a senha" });

  await page.getByLabel("Senha nova").fill("ana.lima-2026");  // contém o nome do e-mail
  const regras = page.getByTestId("regras-da-senha");
  await expect(regras.locator("li").nth(2)).toHaveClass(/text-muted-foreground/);
  await expect(salvar).toBeDisabled();

  await page.getByLabel("Senha nova").fill("Folha-Strass-2026");
  await page.getByLabel("Repita a senha").fill("Folha-Strass-2025");
  await expect(page.getByText("As duas senhas não são iguais.")).toBeVisible();
  await expect(salvar).toBeDisabled();
  await page.getByLabel("Repita a senha").fill("Folha-Strass-2026");
  await expect(regras.locator("li.text-success")).toHaveCount(3);
  await page.screenshot({ path: `${TELAS}/criar-senha-1440.png`, animations: "disabled" });
  await salvar.click();
  await expect(page.getByTestId("senha-salva")).toBeVisible();
  expect(pedidos.find((p) => p.caminho === "/auth/senha")?.corpo).toEqual({ token: "tok-do-email", senha: "Folha-Strass-2026" });
  expect(page.url()).not.toContain("tok-do-email");
  // o token nunca foi na URL de um pedido à API
  expect(pedidos.every((p) => !p.caminho.includes("tok-do-email"))).toBe(true);
  expect(erros).toEqual([]);
});

test("link vencido ou incompleto: pede outro", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await preparar(page, { linkValido: false });
  await page.goto("/redefinir-senha#t=tok-velho");
  await expect(page.getByTestId("link-invalido")).toContainText("Este link já foi usado ou venceu. Peça outro.");
  await page.screenshot({ path: `${TELAS}/link-vencido-1440.png`, animations: "disabled" });
  await page.goto("/redefinir-senha");
  await expect(page.getByTestId("link-invalido")).toContainText("Este link está incompleto.");
  await page.getByRole("link", { name: "Pedir outro link" }).click();
  await expect(page).toHaveURL(/\/esqueci-senha/);
  expect(erros).toEqual([]);
});

test("celular e tema escuro", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { erros } = await preparar(page, { tema: "dark" });
  await page.goto("/login");
  await expect(page.getByTestId("passo-da-senha")).toBeVisible();
  const largura = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(largura).toBeLessThanOrEqual(390);
  await page.screenshot({ path: `${TELAS}/login-celular-escuro.png`, animations: "disabled" });
  await senha(page);
  await expect(page.getByTestId("passo-do-codigo")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/codigo-celular-escuro.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});
