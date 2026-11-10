import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * A API é simulada só aqui dentro. Os horários são relativos ao momento do teste,
 * e cada estado da fila (com previsão, "pelo menos", sem previsão, retomada fixa,
 * job perdido) aparece uma vez para os prints da Fase 3.
 */

const TELAS = "../docs/fase-3-telas";

function emMinutos(agora: number, min: number): string {
  return new Date(agora + min * 60_000).toISOString();
}

function visaoComJobs(agora = Date.now()) {
  return {
    gerado_em: new Date(agora).toISOString(),
    maquinas: [
      {
        id: "maq-01",
        nome: "FOLHA-01",
        online: true,
        sessao_bloqueada: false,
        job_perdido: false,
        capacidade: { interactive: 1, browser: 1, background: 2 },
        rodando: [{ job_id: "job-rodando", pool: "interactive", restante_s: 8 * 60, motivo: null }],
        vagas_tela: 0,
      },
      {
        id: "maq-02",
        nome: "FOLHA-02",
        online: false,
        sessao_bloqueada: false,
        job_perdido: true,
        capacidade: { interactive: 1, browser: 1, background: 2 },
        rodando: [],
        vagas_tela: 0,
      },
      {
        id: "maq-03",
        nome: "FISCAL-01",
        online: true,
        sessao_bloqueada: false,
        job_perdido: false,
        capacidade: { interactive: 1, browser: 1, background: 2 },
        rodando: [],
        vagas_tela: 1,
      },
    ],
    jobs: [
      {
        posicao: 1,
        job_id: "job-a",
        execution_id: "exe-a",
        automation_id: 7,
        automacao: "Integração Contábil · Folha",
        pool: "interactive",
        itens: ["5066"],
        prioridade: 0,
        posicao_manual: null,
        maquina_prevista: "maq-03",
        maquina_prevista_nome: "FISCAL-01",
        maquina_obrigatoria: null,
        inicio_previsto: emMinutos(agora, 0),
        termino_previsto: emMinutos(agora, 23),
        estimativa_s: 23 * 60,
        estimativa_minima_s: null,
        etapas_sem_base: [],
        motivos: [],
        enfileirado_em: emMinutos(agora, -6),
      },
      {
        posicao: 2,
        job_id: "job-b",
        execution_id: "exe-a",
        automation_id: 7,
        automacao: "Integração Contábil · Folha",
        pool: "interactive",
        itens: ["5081", "5076", "5075", "5070", "5069"],
        prioridade: 0,
        posicao_manual: null,
        maquina_prevista: "maq-01",
        maquina_prevista_nome: "FOLHA-01",
        maquina_obrigatoria: null,
        inicio_previsto: emMinutos(agora, 8),
        termino_previsto: emMinutos(agora, 79),
        estimativa_s: 71 * 60,
        estimativa_minima_s: null,
        etapas_sem_base: [],
        motivos: [],
        enfileirado_em: emMinutos(agora, -6),
      },
      {
        posicao: 3,
        job_id: "job-c",
        execution_id: "exe-c",
        automation_id: 9,
        automacao: "Conferência de guias",
        pool: "interactive",
        itens: ["7310"],
        prioridade: 0,
        posicao_manual: null,
        maquina_prevista: "maq-03",
        maquina_prevista_nome: "FISCAL-01",
        maquina_obrigatoria: null,
        inicio_previsto: emMinutos(agora, 23),
        termino_previsto: null,
        estimativa_s: null,
        estimativa_minima_s: 9 * 60,
        etapas_sem_base: ["Exportar relatório"],
        motivos: [
          { codigo: "sem_historico_etapa", texto: "etapa Exportar relatório (item 7310) rodando pela primeira vez, sem histórico de estimativas" },
        ],
        enfileirado_em: emMinutos(agora, -3),
      },
      {
        posicao: 4,
        job_id: "job-d",
        execution_id: "exe-d",
        automation_id: 9,
        automacao: "Conferência de guias",
        pool: "interactive",
        itens: ["7311"],
        prioridade: 0,
        posicao_manual: null,
        maquina_prevista: "maq-03",
        maquina_prevista_nome: "FISCAL-01",
        maquina_obrigatoria: null,
        inicio_previsto: null,
        termino_previsto: null,
        estimativa_s: null,
        estimativa_minima_s: 9 * 60,
        etapas_sem_base: ["Exportar relatório"],
        motivos: [
          { codigo: "aguardando_job_sem_previsao", texto: "aguardando o término de Conferência de guias (7310), que está sem previsão" },
          { codigo: "sem_historico_etapa", texto: "etapa Exportar relatório (item 7311) rodando pela primeira vez, sem histórico de estimativas" },
        ],
        enfileirado_em: emMinutos(agora, -2),
      },
    ],
    perdidos: [
      {
        job_id: "job-perdido",
        execution_id: "exe-p",
        automation_id: 7,
        automacao: "Integração Contábil · Folha",
        itens: [{ chave: "5012" }],
        maquina_id: "maq-02",
        maquina_nome: "FOLHA-02",
        perdido_em: emMinutos(agora, -14),
        motivo: "A instância direta parou de dar sinal no meio do job.",
        estado_central: false,
      },
    ],
  };
}

const VAZIA = () => ({ gerado_em: new Date().toISOString(), maquinas: [], jobs: [], perdidos: [] });

type Chamada = { metodo: string; caminho: string; corpo: unknown };

async function prepararPagina(page: Page, visao: () => unknown, tema: "light" | "dark" = "light") {
  const chamadas: Chamada[] = [];
  const erros: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") erros.push(msg.text());
  });
  page.on("pageerror", (err) => erros.push(String(err)));

  await page.addInitScript(
    ([t]) => {
      window.localStorage.setItem("portal_token", "token-de-teste");
      window.localStorage.setItem("portal_theme", t);
    },
    [tema],
  );
  // O tempo real só chega na Fase 4: o canal legado é recusado e a tela fica na releitura.
  await page.routeWebSocket(/api\.teste\.invalid/, (ws) => ws.close());
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const caminho = new URL(req.url()).pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    chamadas.push({ metodo: req.method(), caminho, corpo });
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (caminho === "/auth/me") {
      return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    }
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/fila" && req.method() === "GET") return json(visao());
    if (caminho.startsWith("/fila/jobs/") && caminho.endsWith("/cancelar")) return json({ job_id: "job-a", status: "cancelled" });
    if (caminho.startsWith("/fila/jobs/") && caminho.endsWith("/decisao")) return json({ job_id: "job-perdido", status: "queued" });
    if (caminho.startsWith("/fila/jobs/") && req.method() === "PATCH") return json({ ...(corpo as object) });
    return json([]);
  });
  return { chamadas, erros };
}

// O botão de desenvolvimento do Next só existe no `next dev`; fora dos prints.
const SEM_INDICADOR_DEV = "nextjs-portal { display: none !important; }";

async function abrirFila(page: Page) {
  await page.goto("/fila");
  await page.addStyleTag({ content: SEM_INDICADOR_DEV });
  await expect(page.getByRole("heading", { name: "Fila", exact: true })).toBeVisible();
}

for (const tema of ["light", "dark"] as const) {
  for (const tela of [
    { nome: "desktop", viewport: { width: 1440, height: 900 } },
    { nome: "celular", viewport: { width: 390, height: 844 } },
  ]) {
    test(`fila com jobs, máquinas e perdido — ${tela.nome}, tema ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
      await page.setViewportSize(tela.viewport);
      const { erros } = await prepararPagina(page, () => visaoComJobs(), tema);
      await abrirFila(page);
      await expect(page.getByTestId("job-na-fila")).toHaveCount(4);
      await expect(page.getByText("FISCAL-01").first()).toBeVisible();
      await expect(page.getByRole("heading", { name: "Jobs perdidos" })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: `${TELAS}/fila-${tela.nome}-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
      expect(erros).toEqual([]);
    });
  }
}

test("Sem previsão aparece sempre com o motivo", async ({ page }) => {
  const { erros } = await prepararPagina(page, () => visaoComJobs());
  await abrirFila(page);
  const linhas = page.getByTestId("job-na-fila");
  await expect(linhas).toHaveCount(4);
  const quantas = await linhas.count();
  let semPrevisao = 0;
  for (let i = 0; i < quantas; i += 1) {
    const linha = linhas.nth(i);
    if ((await linha.getByText("Sem previsão").count()) > 0 || (await linha.getByText("pelo menos").count()) > 0) {
      semPrevisao += 1;
      await expect(linha.getByRole("listitem").first()).toBeVisible();
      await expect(linha).not.toContainText("o portal não informou o motivo");
    }
  }
  expect(semPrevisao).toBe(2);
  await expect(linhas.nth(3)).toContainText("aguardando o término de Conferência de guias (7310), que está sem previsão");
  await expect(linhas.nth(3)).toContainText("rodando pela primeira vez, sem histórico de estimativas");
  expect(erros).toEqual([]);
});

test("cancelar mostra o efeito antes e só então chama a API", async ({ page }) => {
  const { chamadas, erros } = await prepararPagina(page, () => visaoComJobs());
  await abrirFila(page);
  await page.getByTestId("job-na-fila").first().getByRole("button", { name: /Cancelar/ }).click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("Cancelar este job?");
  await expect(dialogo).toContainText("O job ainda não começou, então nada é desfeito em nenhuma máquina.");
  expect(chamadas.filter((c) => c.metodo === "POST")).toEqual([]);
  await page.screenshot({ path: `${TELAS}/fila-confirmar-cancelamento.png`, animations: "disabled" });
  await dialogo.getByRole("button", { name: "Cancelar job" }).click();
  await expect.poll(() => chamadas.filter((c) => c.metodo === "POST").map((c) => c.caminho)).toEqual(["/fila/jobs/job-a/cancelar"]);
  expect(erros).toEqual([]);
});

test("subir prioridade manda o novo valor", async ({ page }) => {
  const { chamadas, erros } = await prepararPagina(page, () => visaoComJobs());
  await abrirFila(page);
  await page.getByTestId("job-na-fila").nth(1).getByRole("button", { name: "Subir prioridade" }).click();
  await expect
    .poll(() => chamadas.filter((c) => c.metodo === "PATCH"))
    .toEqual([{ metodo: "PATCH", caminho: "/fila/jobs/job-b", corpo: { prioridade: 1 } }]);
  expect(erros).toEqual([]);
});

test("job perdido: continuar explica que só volta na mesma máquina", async ({ page }) => {
  const { chamadas, erros } = await prepararPagina(page, () => visaoComJobs());
  await abrirFila(page);
  await page.getByRole("button", { name: "Continuar" }).click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("só em FOLHA-02, porque o progresso ficou nela");
  await expect(dialogo).toContainText("confira na máquina se a automação não ficou parada no meio de uma tela");
  await page.screenshot({ path: `${TELAS}/fila-confirmar-continuar.png`, animations: "disabled" });
  await dialogo.getByRole("button", { name: "Continuar" }).click();
  await expect
    .poll(() => chamadas.filter((c) => c.metodo === "POST"))
    .toEqual([{ metodo: "POST", caminho: "/fila/jobs/job-perdido/decisao", corpo: { decisao: "continuar" } }]);
  expect(erros).toEqual([]);
});

test("fila vazia e sem máquinas explica o que falta", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { erros } = await prepararPagina(page, VAZIA);
  await abrirFila(page);
  await expect(page.getByText("Fila vazia")).toBeVisible();
  await expect(page.getByText("Nenhuma máquina disponível para a fila")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/fila-vazia.png`, fullPage: true, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("o painel inicial também ganhou a identidade Biason", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await prepararPagina(page, () => visaoComJobs());
  await page.goto("/dashboard");
  await page.addStyleTag({ content: SEM_INDICADOR_DEV });
  await expect(page.getByAltText("Biason")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const fonte = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
  expect(fonte).toContain("Barlow");
  await page.screenshot({ path: `${TELAS}/dashboard-claro.png`, animations: "disabled" });
});
