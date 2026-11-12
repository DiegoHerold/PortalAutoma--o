import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Agendamentos como agenda (12/11/2026): só o calendário; clicar num horário vazio cria, arrastar
 * move, clicar abre o cartão com Editar. A API é simulada só aqui. As datas ficam sempre numa
 * semana futura (a ocorrência que já passou não se arrasta).
 */

const TELAS = "../docs/agenda-telas";
mkdirSync(TELAS, { recursive: true });

const pad = (n: number) => String(n).padStart(2, "0");
const chave = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
function semanaFutura(): string[] {
  const hoje = new Date();
  const segunda = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - ((hoje.getDay() + 6) % 7) + 14);
  return Array.from({ length: 7 }, (_, i) => chave(new Date(segunda.getFullYear(), segunda.getMonth(), segunda.getDate() + i)));
}
const DIAS = semanaFutura();  // segunda .. domingo daqui a duas semanas

const base = { target_type: "automation", target_id: "7", target_version: null, schedule_execution_id: null, flow_execution_id: null,
  actual_start: null, actual_end: null, reason: null, progress: null, responsible: null, agent: null, duration_seconds: null,
  estimated_duration_seconds: 3600, estimation_confidence: null, is_estimated: true, timezone: "America/Sao_Paulo", is_one_time: false };
const ITENS = [
  { ...base, id: "occ_semanal", schedule_id: 5, execution_id: null, target_name: "Integração Contábil · Folha", schedule_name: "Folha de segunda e quarta",
    planned_start: `${DIAS[0]}T10:00:00-03:00`, effective_end: `${DIAS[0]}T11:00:00-03:00`, status: "scheduled", temporal_status: "future_scheduled",
    recurrence_type: "weekly", schedule_type: "cron" },
  { ...base, id: "occ_semanal_qua", schedule_id: 5, execution_id: null, target_name: "Integração Contábil · Folha", schedule_name: "Folha de segunda e quarta",
    planned_start: `${DIAS[2]}T10:00:00-03:00`, effective_end: `${DIAS[2]}T11:00:00-03:00`, status: "scheduled", temporal_status: "future_scheduled",
    recurrence_type: "weekly", schedule_type: "cron" },
  { ...base, id: "occ_unica", schedule_id: 6, execution_id: null, target_name: "Conferência de guias", schedule_name: null,
    planned_start: `${DIAS[1]}T14:00:00-03:00`, effective_end: `${DIAS[1]}T14:30:00-03:00`, status: "scheduled", temporal_status: "future_scheduled",
    recurrence_type: "once", schedule_type: "once", is_one_time: true, estimated_duration_seconds: 1800 },
  { ...base, id: "occ_rodou", schedule_id: 8, execution_id: "exe_1", target_name: "Relatório de férias", schedule_name: null,
    planned_start: `${DIAS[1]}T10:30:00-03:00`, effective_end: `${DIAS[1]}T11:30:00-03:00`, status: "succeeded", temporal_status: "past_succeeded",
    recurrence_type: "daily", schedule_type: "cron" },
];
const agendamento = (id: number, campos: Record<string, unknown>) => ({ id, automation_id: 7, automation_version_id: null, flow_id: null,
  flow_version_id: null, target_type: "automation", key: null, name: null, cron_expression: null, timezone: "America/Sao_Paulo", is_active: true,
  recurrence_type: "daily", time_of_day: "10:00", weekdays: null, day_of_month: null, specific_date: null, is_one_time: false,
  last_dispatched_at: null, status: "active", schedule_type: "cron", interval_seconds: null, payload: {}, misfire_policy: "run_once_now",
  max_catch_up_runs: 1, misfire_grace_seconds: 3600, overlap_policy: "forbid", next_run_at: null, last_run_at: null, ...campos });
const AGENDAMENTOS: Record<string, unknown> = {
  "5": agendamento(5, { name: "Folha de segunda e quarta", recurrence_type: "weekly", weekdays: [0, 2] }),
  "6": agendamento(6, { recurrence_type: "once", schedule_type: "once", specific_date: DIAS[1], time_of_day: "14:00", is_one_time: true }),
  "8": agendamento(8, {}),
};

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
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho: caminho + url.search, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "admin@teste.invalid", name: "Admin de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/schedules/calendar") return json({ range: { date_from: url.searchParams.get("from"), date_to: url.searchParams.get("to"), timezone: "America/Sao_Paulo" },
      items: ITENS, density: [], summary: { total: 4, completed: 1, running: 0, failed: 0, future: 3, cancelled: 0, skipped: 0, peak_from: null, peak_to: null, peak_count: 0 } });
    const um = caminho.match(/^\/schedules\/(\d+)$/);
    if (um) return json(req.method() === "GET" ? AGENDAMENTOS[um[1]] : { ...(AGENDAMENTOS[um[1]] as object), ...(corpo as object) });
    if (/^\/schedules\/\d+\/history$/.test(caminho)) return json([]);
    if (caminho === "/schedules/preview") return json({ occurrences: [] });
    if (caminho === "/automations") return json([{ id: 7, name: "Integração Contábil · Folha", slug: "ic", category_id: 1, executor_type: "direto",
      default_priority: "normal", timeout_seconds: 300, max_retries: 0, is_active: true }]);
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.evaluate(() => document.fonts.ready);
}

/** Leva a hora pedida para a área visível e devolve o ponto (dentro da coluna do dia) dessa hora. */
async function pontoDaHora(page: Page, dia: string, hora: number) {
  const coluna = page.locator(`[data-dia="${dia}"]`);
  const altura = (await coluna.boundingBox())!.height;
  await page.getByTestId("grade-de-horas").locator(".overflow-y-auto").evaluate((el, y) => { el.scrollTop = y - 200; }, (hora / 24) * altura);
  return { coluna, posicao: { x: 30, y: (hora / 24) * altura + 4 } };
}

for (const tema of ["light", "dark"] as const) {
  test(`semana: só o calendário, blocos no horário e a cor pela situação — ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    const { erros } = await preparar(page, tema);
    await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
    const grade = page.getByTestId("grade-de-horas");
    await expect(grade.locator("[data-ocorrencia]")).toHaveCount(4);
    await expect(grade.locator(`[data-dia="${DIAS[0]}"]`).getByText("Folha de segunda e quarta")).toBeVisible();
    await expect(grade.locator("[data-ocorrencia='8']")).toHaveAttribute("draggable", "false");  // já rodou: não arrasta
    await expect(grade.locator("[data-ocorrencia='6']")).toHaveAttribute("draggable", "true");
    await page.locator(`[data-dia="${DIAS[0]}"]`).evaluate((el) => el.scrollIntoView({ block: "center" }));
    await page.getByTestId("grade-de-horas").locator(".overflow-y-auto").evaluate((el) => { el.scrollTop = el.scrollHeight * (7.5 / 24); });
    await page.screenshot({ path: `${TELAS}/semana-${tema === "light" ? "claro" : "escuro"}.png`, animations: "disabled" });
    expect(erros).toEqual([]);
  });
}

test("clicar num horário vazio abre o novo agendamento com o dia e a hora", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const { coluna, posicao } = await pontoDaHora(page, DIAS[3], 15);
  await coluna.click({ position: posicao });
  await expect(page.locator("#s-date")).toHaveValue(DIAS[3]);
  await expect(page.locator("#s-time")).toHaveValue("15:00");
  expect(erros).toEqual([]);
});

test("arrastar uma ocorrência única muda a data e a hora na hora", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const bloco = page.getByTestId("grade-de-horas").locator("[data-ocorrencia='6']");
  await bloco.evaluate((el) => el.scrollIntoView({ block: "center" }));
  const { coluna, posicao } = await pontoDaHora(page, DIAS[4], 16);
  await bloco.dragTo(coluna, { sourcePosition: { x: 10, y: 4 }, targetPosition: posicao });
  await expect.poll(() => pedidos.find((p) => p.metodo !== "GET" && p.caminho === "/schedules/6")?.corpo)
    .toMatchObject({ recurrence_type: "once", specific_date: DIAS[4], time_of_day: "16:00" });
  expect(erros).toEqual([]);
});

test("arrastar uma ocorrência que se repete pergunta antes e mostra o antes e o depois", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const bloco = page.getByTestId("grade-de-horas").locator(`[data-dia="${DIAS[2]}"] [data-ocorrencia='5']`);
  await bloco.evaluate((el) => el.scrollIntoView({ block: "center" }));
  const { coluna, posicao } = await pontoDaHora(page, DIAS[4], 9);
  await bloco.dragTo(coluna, { sourcePosition: { x: 10, y: 4 }, targetPosition: posicao });
  const confirmacao = page.getByTestId("confirmar-mudanca");
  await expect(confirmacao.getByText("Toda segunda e quarta às 10:00")).toBeVisible();
  await expect(confirmacao.getByText("Toda segunda e sexta às 09:00")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/confirmar-mudanca.png`, animations: "disabled" });
  expect(pedidos.some((p) => p.metodo !== "GET" && p.caminho === "/schedules/5")).toBe(false);  // nada antes de confirmar
  await page.getByRole("button", { name: "Mudar todas" }).click();
  await expect.poll(() => pedidos.find((p) => p.metodo !== "GET" && p.caminho === "/schedules/5")?.corpo)
    .toMatchObject({ recurrence_type: "weekly", weekdays: [0, 4], time_of_day: "09:00" });
  expect(erros).toEqual([]);
});

test("clicar numa ocorrência abre o cartão; Editar abre o agendamento", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const bloco = page.getByTestId("grade-de-horas").locator(`[data-dia="${DIAS[0]}"] [data-ocorrencia='5']`);
  await bloco.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await bloco.click();
  const cartao = page.getByTestId("cartao-ocorrencia");
  await expect(cartao.getByText("Toda segunda e quarta às 10:00")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/cartao.png`, animations: "disabled" });
  await cartao.getByRole("button", { name: "Editar" }).click();
  await expect(cartao).toHaveCount(0);
  await expect(page.locator("#s-time")).toHaveValue("10:00");
  expect(erros).toEqual([]);
});

test("mês: ocorrências em cada dia, clicar no vazio cria e arrastar muda o dia", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, `/schedules?visao=mes&data=${DIAS[0]}`);
  const mes = page.getByTestId("grade-do-mes");
  await expect(mes.locator(`[data-dia="${DIAS[1]}"] [data-ocorrencia]`)).toHaveCount(2);
  await page.screenshot({ path: `${TELAS}/mes.png`, animations: "disabled" });
  await mes.locator(`[data-dia="${DIAS[1]}"] [data-ocorrencia='6']`).dragTo(mes.locator(`[data-dia="${DIAS[5]}"]`), { targetPosition: { x: 40, y: 100 } });
  await expect.poll(() => pedidos.find((p) => p.metodo !== "GET" && p.caminho === "/schedules/6")?.corpo)
    .toMatchObject({ specific_date: DIAS[5], time_of_day: "14:00" });
  await mes.locator(`[data-dia="${DIAS[6]}"]`).click({ position: { x: 40, y: 110 } });
  await expect(page.locator("#s-date")).toHaveValue(DIAS[6]);
  expect(erros).toEqual([]);
});

test("visões e navegação: Hoje, anterior e próximo pelo endereço", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  await page.getByRole("button", { name: "Próximo" }).click();
  await expect(page).toHaveURL(new RegExp(`data=${chave(new Date(Number(DIAS[0].slice(0, 4)), Number(DIAS[0].slice(5, 7)) - 1, Number(DIAS[0].slice(8)) + 7))}`));
  await page.getByRole("tab", { name: "Dia" }).click();
  await expect(page.getByTestId("grade-de-horas").locator("[data-dia]")).toHaveCount(1);
  await page.getByRole("button", { name: "Hoje" }).click();
  await expect(page).toHaveURL(new RegExp(`data=${chave(new Date())}`));
  expect(erros).toEqual([]);
});

test("clicar e arrastar num espaço vazio seleciona o intervalo e cria a partir do início", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const { coluna, posicao } = await pontoDaHora(page, DIAS[3], 9);
  const caixa = (await coluna.boundingBox())!;
  const alturaHora = caixa.height / 24;
  await page.mouse.move(caixa.x + 30, caixa.y + posicao.y);
  await page.mouse.down();
  await page.mouse.move(caixa.x + 30, caixa.y + posicao.y + alturaHora * 2.4, { steps: 6 });
  await expect(page.getByTestId("selecao-de-horario")).toHaveText("09:00 – 11:30");
  await page.screenshot({ path: `${TELAS}/selecionar-intervalo.png`, animations: "disabled" });
  await page.mouse.up();
  await expect(page.locator("#s-date")).toHaveValue(DIAS[3]);
  await expect(page.locator("#s-time")).toHaveValue("09:00");
  expect(erros).toEqual([]);
});

test("abre focado das 8 h às 18 h; Ctrl + roda estica as horas e fica guardado", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  const rolagem = page.getByTestId("rolagem-horas");
  const grade = rolagem.locator("[data-altura-hora]");
  await expect.poll(() => rolagem.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);  // altura calculada e rolada
  const antes = Number(await grade.getAttribute("data-altura-hora"));
  expect(await rolagem.evaluate((el) => el.scrollTop)).toBeCloseTo(8 * antes, -1);  // 08:00 no topo
  const visivelHoras = (await rolagem.evaluate((el) => el.clientHeight)) / antes;
  expect(visivelHoras).toBeGreaterThanOrEqual(10);  // cabe das 8 às 18
  const caixa = (await rolagem.boundingBox())!;
  await page.mouse.move(caixa.x + 400, caixa.y + 200);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -200);
  await page.keyboard.up("Control");
  await expect.poll(async () => Number(await grade.getAttribute("data-altura-hora"))).toBeGreaterThan(antes);
  const depois = Number(await grade.getAttribute("data-altura-hora"));
  await page.reload();
  await expect.poll(async () => Number(await page.getByTestId("rolagem-horas").locator("[data-altura-hora]").getAttribute("data-altura-hora"))).toBe(depois);
  await page.getByRole("button", { name: "Encolher as horas" }).click();
  await expect.poll(async () => Number(await page.getByTestId("rolagem-horas").locator("[data-altura-hora]").getAttribute("data-altura-hora"))).toBeLessThan(depois);
  expect(erros).toEqual([]);
});

test("cabeçalho da semana abre o dia; no dia, os dias vizinhos ficam nas laterais", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=semana&data=${DIAS[0]}`);
  await page.locator(`[data-cabecalho="${DIAS[2]}"]`).click();
  await expect(page).toHaveURL(new RegExp(`visao=dia&data=${DIAS[2]}|data=${DIAS[2]}.*visao=dia`));
  await expect(page.getByTestId("grade-de-horas").locator("[data-dia]")).toHaveCount(1);
  await expect(page.getByTestId("dia-anterior")).toContainText("TER");
  await expect(page.getByTestId("dia-seguinte")).toContainText("QUI");
  // a grade inteira, com o rodapé de dicas, cabe numa tela de 1080
  const rodape = page.getByRole("button", { name: "Esticar as horas" });
  expect((await rodape.boundingBox())!.y + 40).toBeLessThanOrEqual(1080);
  await page.screenshot({ path: `${TELAS}/dia.png`, animations: "disabled" });
  await page.getByTestId("dia-seguinte").click();
  await expect(page.getByTestId("grade-de-horas").locator(`[data-dia="${DIAS[3]}"]`)).toBeVisible();
  await page.getByTestId("dia-anterior").click();
  await page.getByTestId("dia-anterior").click();
  await expect(page.getByTestId("grade-de-horas").locator(`[data-dia="${DIAS[1]}"]`)).toBeVisible();
  expect(erros).toEqual([]);
});

test("mês: dois cliques num dia abrem o dia (e não criam)", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { erros } = await preparar(page);
  await abrir(page, `/schedules?visao=mes&data=${DIAS[0]}`);
  await page.getByTestId("grade-do-mes").locator(`[data-dia="${DIAS[4]}"]`).dblclick({ position: { x: 40, y: 110 } });
  await expect(page.getByTestId("grade-de-horas").locator(`[data-dia="${DIAS[4]}"]`)).toBeVisible();
  await page.waitForTimeout(400);
  await expect(page.locator("#s-date")).toHaveCount(0);
  expect(erros).toEqual([]);
});
