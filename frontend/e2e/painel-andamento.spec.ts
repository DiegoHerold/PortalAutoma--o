import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Painel com o foco no que está em andamento (12/11/2026): as máquinas são abas de filtro; depois,
 * na ordem, o que roda agora, o que está pausado/esperando, o que espera para começar (fila e
 * perdidos) e, por último, as últimas automações. API simulada só aqui.
 */

const TELAS = "../docs/painel-andamento-telas";
mkdirSync(TELAS, { recursive: true });

function execucao(em: (s: number) => string, id: string, automacao: string, maquina: string, extra: Record<string, unknown> = {}) {
  return {
    execucao_id: id, job_id: `job_${id}`, automation_id: 7, automacao, maquina_id: `mch_${maquina}`, maquina: maquina,
    modo: "direct", itens: [{ chave: "5066", rotulo: "Empresa 5066" }], tentativa: 1, desde: em(-600), decorrido_s: 600,
    falta_s: 900, motivo_sem_previsao: null, termino_previsto: em(900), etapa: { etapa: "rubricas", item: "5066" },
    item: { item: "5066", rotulo: "Empresa 5066" }, progresso: { atual: 12, total: 40, rotulo: null }, pausa: null, atencoes: 0,
    situacao: null, pode_controlar: true, pode_ver_tela: false, tela: null, log: null, ...extra,
  };
}

function maquina(id: string, extra: Record<string, unknown> = {}) {
  return { id: `mch_${id}`, nome: id, online: true, sessao_bloqueada: false, job_perdido: false, ocupada: false, rodando: null,
           proximo: null, ...extra };
}

async function preparar(page: Page, vazio = false) {
  const pedidos: string[] = [];
  const erros: string[] = [];
  page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.addInitScript(() => {
    window.localStorage.setItem("portal_token", "token-de-teste");
    window.localStorage.setItem("portal_theme", "dark");
  });
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  const agora = Date.now();
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const url = new URL(route.request().url());
    const caminho = url.pathname.replace("/api/v1", "");
    pedidos.push(caminho + url.search);
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "ti@teste.invalid", name: "TI Biason", role: "operator", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/painel") return json({
      gerado_em: em(0), central: false, fila: { esperando: 1, perdidos: 1, termina_em: null, sem_previsao: 0 },
      maquinas: [maquina("MAQ10", { ocupada: true }), maquina("MAQ77", { ocupada: true }), maquina("MAQ36", { online: false, job_perdido: true })],
      execucoes: vazio ? [] : [
        execucao(em, "exe_a", "Integração Contábil · Folha", "MAQ10"),
        execucao(em, "exe_b", "Conferência de guias", "MAQ77", { situacao: { tipo: "espera", rotulo: "Domínio carregando", desde: em(-240) } }),
      ],
      aguardando: vazio ? { fila: [], perdidos: [] } : {
        fila: [{ job_id: "job_f", execucao_id: "exe_f", automation_id: 9, automacao: "Relatório de férias", itens: ["7310", "7311"],
                 maquina_id: "mch_MAQ10", maquina: "MAQ10", inicio_previsto: em(900), enfileirado_em: em(-60), motivos: ["Máquina ocupada"] }],
        perdidos: [{ job_id: "job_p", execucao_id: "exe_p", automation_id: 7, automacao: "Integração Contábil · Folha", itens: ["5081"],
                     maquina_id: "mch_MAQ36", maquina: "MAQ36", perdido_em: em(-1800) }],
      },
    });
    if (caminho === "/painel/recentes") return json({ maquinas: [], automacoes: [
      { automation_id: 7, automacao: "Integração Contábil · Folha", pode_executar: true, pode_controlar: true,
        ultima: { execucao_id: "exe_0", status: "succeeded", quando: em(-7200), maquinas: ["MAQ10"], itens: ["5081"], continuada_em: null } }] });
    if (/\/execucoes\/\w+\/acompanhar$/.test(caminho)) return route.fulfill({ status: 404, body: "{}" });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page) {
  await page.goto("/dashboard");
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("painel: andamento primeiro, na ordem pedida; últimas automações por último", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page);
  await expect(page.getByTestId("secao-esperando")).toBeVisible();
  // A ordem na página: abas, rodando, pausadas/esperando, esperando para começar, últimas automações.
  const ordem = await page.locator("[role=tablist][aria-label='Máquina'], [data-testid^='secao-'], [data-testid='ultimas-automacoes']")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid") ?? "abas"));
  expect(ordem).toEqual(["abas", "secao-rodando", "secao-paradas", "secao-esperando", "ultimas-automacoes"]);
  await expect(page.getByTestId("secao-rodando").getByTestId("monitor")).toHaveCount(1);
  await expect(page.getByTestId("secao-paradas").getByTestId("situacao")).toContainText("Esperando: Domínio carregando");
  const esperando = page.getByTestId("esperando");
  await expect(esperando.locator("[data-job='job_p']")).toContainText("Perdida em MAQ36");
  await expect(esperando.locator("[data-job='job_p']")).toContainText("esperando uma decisão");
  await expect(esperando.locator("[data-job='job_f']")).toContainText("Começa às");
  // A seção de máquinas do pé da página virou as abas.
  await expect(page.getByRole("heading", { name: "Máquinas" })).toHaveCount(0);
  const abas = page.getByRole("tablist", { name: "Máquina" });
  await expect(abas.getByRole("tab")).toHaveCount(4);
  await expect(abas.getByRole("tab", { name: /MAQ36/ })).toContainText("sem sinal");
  await page.screenshot({ path: `${TELAS}/painel-1920-escuro.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("painel: a aba da máquina filtra o andamento, a espera e as últimas automações, e fica guardada", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page);
  const abas = page.getByRole("tablist", { name: "Máquina" });
  await abas.getByRole("tab", { name: /MAQ10/ }).click();
  await expect(page.getByTestId("secao-rodando").getByTestId("monitor")).toHaveCount(1);
  await expect(page.getByTestId("secao-paradas")).toHaveCount(0);  // a de espera é da MAQ77
  await expect(page.getByTestId("esperando").locator("[data-job]")).toHaveCount(1);  // só a fila da MAQ10
  await expect.poll(() => pedidos.some((p) => p === "/painel/recentes?limite=3&maquina=mch_MAQ10")).toBe(true);

  await abas.getByRole("tab", { name: /MAQ36/ }).click();
  await expect(page.getByTestId("secao-rodando")).toHaveCount(0);
  await expect(page.getByTestId("esperando").locator("[data-job='job_p']")).toBeVisible();
  await page.reload();
  await expect(abas.getByRole("tab", { name: /MAQ36/ })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: `${TELAS}/painel-maquina-36.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("painel: nada em andamento mostra só o aviso e as últimas automações", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page, true);
  await abrir(page);
  await expect(page.getByTestId("nada-rodando")).toContainText("Nada rodando agora");
  await expect(page.locator("[data-testid^='secao-']")).toHaveCount(0);
  await expect(page.getByTestId("ultimas-automacoes").locator("[data-automacao]")).toHaveCount(1);
  expect(erros).toEqual([]);
});
