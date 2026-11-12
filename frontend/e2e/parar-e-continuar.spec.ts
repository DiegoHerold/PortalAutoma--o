import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Parar (depois do item ou agora) e continuar uma execução cancelada; e a linha única que diz por
 * que uma execução não anda (cancelando, parando, pausa, espera, sem sinal). API simulada só aqui.
 */

const TELAS = "../docs/parar-e-continuar-telas";
mkdirSync(TELAS, { recursive: true });

type Pedido = { metodo: string; caminho: string; corpo: unknown };

function ao(em: (s: number) => string, id: string, automacao: string, extra: Record<string, unknown>) {
  return {
    execucao_id: id, job_id: `job_${id}`, automation_id: 7, automacao, maquina_id: `mch_${id}`, maquina: `FOLHA-${id.slice(-1)}`,
    modo: "direct", itens: [{ chave: "5066", rotulo: "Empresa 5066" }], tentativa: 1, desde: em(-900), decorrido_s: 900,
    falta_s: 600, motivo_sem_previsao: null, termino_previsto: em(600), etapa: { etapa: "rubricas", item: "5066" },
    item: { item: "5066", rotulo: "Empresa 5066" }, progresso: { atual: 18, total: 50, rotulo: null }, pausa: null, atencoes: 0,
    situacao: null, pode_controlar: true, pode_ver_tela: false, tela: null, log: null, ...extra,
  };
}

function acompanhamento(agora: number, status: "running" | "cancelled", extra: Record<string, unknown> = {}) {
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  return {
    gerado_em: new Date(agora).toISOString(),
    execucao: { id: "exe_1", status, criada_em: em(-900), iniciada_em: em(-840), concluida_em: status === "running" ? null : em(-10),
                falha: null, solicitante: "1", continua_de: null, continuada_em: null },
    situacao: null,
    automacao: { id: 7, nome: "Integração Contábil · Folha", versao: "2.0.0" },
    pode: { ver_telas_e_logs: false, controlar: true },
    rodando: status === "running", decorrido_s: 840, falta_s: null, termino_previsto: null,
    jobs: [{ job_id: "job_1", status, pool: "interactive", itens: ["5081", "5076", "5077"], maquina_id: "mch_1", maquina_nome: "FOLHA-01",
             modo: "direct", tentativa: 1, desde: em(-840), falta_s: null, motivo_sem_previsao: null, termino_previsto: null, falha: null }],
    agora: { etapa_atual: null, item_atual: null, progresso: null, pausa: null, conclusao: null, tela: null, passos: [], atencoes: [] },
    estimativa: { jobs: [] },
    ...extra,
  };
}

async function preparar(page: Page, estado: { acompanhar?: () => unknown; painel?: (em: (s: number) => string) => unknown } = {}) {
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
  await page.route(`${API_DE_TESTE}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const caminho = url.pathname.replace("/api/v1", "");
    const corpo = req.postData() ? JSON.parse(req.postData()!) : null;
    pedidos.push({ metodo: req.method(), caminho, corpo });
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "operator", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/governance/auditoria/tela") return route.fulfill({ status: 204 });
    if (caminho === "/painel" && estado.painel) return json(estado.painel(em));
    if (caminho === "/painel") return json({ gerado_em: em(0), central: false, fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 },
      maquinas: [], execucoes: [
        ao(em, "exe_a", "Integração Contábil · Folha", {}),
        ao(em, "exe_b", "Conferência de guias", { situacao: { tipo: "espera", rotulo: "Domínio abrindo a empresa", desde: em(-420) } }),
        ao(em, "exe_c", "Relatório de férias", { situacao: { tipo: "sem_sinal", desde: em(-840) }, pode_controlar: false }),
        ao(em, "exe_d", "Exportar balancetes", { situacao: { tipo: "cancelando", desde: em(-30), recebido: true } }),
      ] });
    if (caminho === "/painel/recentes") return json({ maquinas: [], automacoes: [
      { automation_id: 7, automacao: "Integração Contábil · Folha", pode_executar: true, pode_controlar: true,
        ultima: { execucao_id: "exe_1", status: "cancelled", quando: em(-600), maquinas: ["FOLHA-01"], itens: ["5081", "5076", "5077"], continuada_em: null } },
      { automation_id: 9, automacao: "Conferência de guias", pode_executar: true, pode_controlar: true,
        ultima: { execucao_id: "exe_2", status: "cancelled", quando: em(-900), maquinas: ["FISCAL-01"], itens: ["7310"], continuada_em: "exe_3" } },
    ] });
    if (/^\/fila\/execucoes\/\w+\/encerrar$/.test(caminho)) return json({ execution_id: "exe_f", encerradas: 1 });
    if (/^\/fila\/execucoes\/\w+\/parar$/.test(caminho)) return json({ execution_id: "exe_a", modo: corpo?.modo, canceladas_na_fila: 0, avisadas: 1, no_agent: 0 });
    if (caminho === "/fila/execucoes/exe_1/continuar" && req.method() === "GET") return json({
      execution_id: "exe_1", pode: true, motivo: null, continuada_em: null, pular: 1, sem_itens: false,
      refazer: [{ chave: "5076", rotulo: "Filial A", situacao: "cancelado" }, { chave: "5077", rotulo: "Filial B", situacao: "pendente" }] });
    if (caminho === "/fila/execucoes/exe_1/continuar") return json({ execution_id: "exe_nova", jobs: [], continua_de: "exe_1", itens: 2, pulados: 1 }, 201);
    if (caminho === "/execucoes/exe_1/acompanhar") return json(estado.acompanhar ? estado.acompanhar() : acompanhamento(agora, "running"));
    if (caminho === "/execucoes/exe_nova/acompanhar") return json({ ...acompanhamento(agora, "running"),
      execucao: { ...acompanhamento(agora, "running").execucao, id: "exe_nova", continua_de: "exe_1" } });
    const outra = caminho.match(/^\/execucoes\/(\w+)\/acompanhar$/);
    if (outra) return json({ ...acompanhamento(agora, "running"), execucao: { ...acompanhamento(agora, "running").execucao, id: outra[1] } });
    if (/\/execucoes\/\w+\/logs$/.test(caminho)) return json({ logs: [], cursor: null });
    if (caminho === "/notificacoes") return json({ avisos: [], nao_lidas: 0 });
    return json([]);
  });
  return { pedidos, erros };
}

async function abrir(page: Page, rota: string) {
  await page.goto(rota);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("painel: uma linha só diz por que a execução não anda, e Parar pede como parar", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const monitores = page.getByTestId("monitor");
  await expect(monitores).toHaveCount(4);
  // Rodando normal não ganha linha nenhuma.
  await expect(monitores.nth(0).getByTestId("situacao")).toHaveCount(0);
  await expect(monitores.nth(1).getByTestId("situacao")).toContainText(/Esperando: Domínio abrindo a empresa · há (7|8) min/);
  await expect(monitores.nth(2).getByTestId("situacao")).toContainText(/Sem sinal da automação há (14|15) min/);
  await expect(monitores.nth(3).getByTestId("situacao")).toContainText("Cancelando");
  // Sem "Parar e retomar execuções" não há botão; cancelando também não.
  await expect(monitores.nth(2).getByRole("button", { name: "Parar a execução" })).toHaveCount(0);
  await expect(monitores.nth(3).getByRole("button", { name: "Parar a execução" })).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/painel-situacoes-1920.png`, fullPage: true, animations: "disabled" });

  await monitores.nth(0).getByRole("button", { name: "Parar a execução" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);  // o botão não abre o cartão
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("Parar depois do item atual");
  await expect(dialogo.getByRole("radio", { name: /Parar depois do item atual/ })).toBeChecked();
  await page.screenshot({ path: `${TELAS}/parar-escolha.png`, animations: "disabled" });
  await dialogo.getByRole("button", { name: "Parar depois do item" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/fila/execucoes/exe_a/parar")?.corpo).toEqual({ modo: "apos_item" });
  await expect(dialogo).toHaveCount(0);

  await monitores.nth(1).getByRole("button", { name: "Parar a execução" }).click();
  await page.getByRole("radio", { name: /Cancelar agora/ }).check();
  await page.getByRole("dialog").getByRole("button", { name: "Cancelar agora" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/fila/execucoes/exe_b/parar")?.corpo).toEqual({ modo: "agora" });

  // O cartão continua levando ao Acompanhar.
  await monitores.nth(0).getByRole("link", { name: "Acompanhar Integração Contábil · Folha" }).click();
  await expect(page).toHaveURL(/\/execucoes\/exe_a$/);
  expect(erros).toEqual([]);
});

test("painel: a última foi cancelada -> Continuar mostra o que roda de novo e abre a nova execução", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page);
  await abrir(page, "/dashboard");
  const recentes = page.getByTestId("ultimas-automacoes");
  await expect(recentes.locator("[data-automacao='7']").getByTestId("continuar")).toBeVisible();
  // Já continuada: não oferece de novo, mostra para onde foi.
  await expect(recentes.locator("[data-automacao='9']").getByTestId("continuar")).toHaveCount(0);
  await expect(recentes.locator("[data-automacao='9']").getByRole("link", { name: "Ver a continuação" })).toHaveAttribute("href", "/execucoes/exe_3");

  await recentes.locator("[data-automacao='7']").getByTestId("continuar").click();
  const previa = page.getByTestId("previa-continuar");
  await expect(previa).toContainText("só com 2 itens");
  await expect(previa).toContainText("pula o que já deu certo");
  await expect(previa.getByRole("listitem")).toHaveCount(2);
  await expect(previa).toContainText("interrompido");
  await expect(previa).toContainText("não começou");
  await page.screenshot({ path: `${TELAS}/continuar-previa.png`, animations: "disabled" });
  await page.getByRole("dialog").getByRole("button", { name: "Continuar" }).click();
  await expect(page).toHaveURL(/\/execucoes\/exe_nova$/);
  expect(pedidos.filter((p) => p.metodo === "POST" && p.caminho === "/fila/execucoes/exe_1/continuar")).toHaveLength(1);
  await expect(page.getByTestId("continuacao")).toContainText("Continua a execução");
  expect(erros).toEqual([]);
});

test("acompanhar: Parar enquanto roda, linha de situação e Continuar quando cancelada", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let status: "running" | "cancelled" = "running";
  const { pedidos, erros } = await preparar(page, {
    acompanhar: () => acompanhamento(Date.now(), status, status === "running"
      ? { situacao: { tipo: "parando", desde: new Date().toISOString(), recebido: true } } : {}),
  });
  await abrir(page, "/execucoes/exe_1");
  await expect(page.getByTestId("situacao")).toContainText("Para ao terminar o item atual");
  await page.getByRole("button", { name: "Parar a execução" }).click();
  // Já vai parar depois do item: só resta cancelar agora.
  await expect(page.getByRole("radio")).toHaveCount(1);
  await expect(page.getByRole("radio", { name: /Cancelar agora/ })).toBeChecked();
  await page.getByRole("dialog").getByRole("button", { name: "Cancelar agora" }).click();
  await expect.poll(() => pedidos.find((p) => p.caminho === "/fila/execucoes/exe_1/parar")?.corpo).toEqual({ modo: "agora" });

  status = "cancelled";
  await page.reload();
  await expect(page.getByRole("button", { name: "Parar a execução" })).toHaveCount(0);
  await expect(page.getByTestId("continuar")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/acompanhar-cancelada.png`, animations: "disabled" });
  expect(erros).toEqual([]);
});

test("painel: comunicação não ativa e cancelamento sem resposta, com Encerrar no Portal", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { pedidos, erros } = await preparar(page, {
    painel: (em) => ({ gerado_em: em(0), central: false, fila: { esperando: 0, perdidos: 0, termina_em: null, sem_previsao: 0 }, maquinas: [],
      execucoes: [
        ao(em, "exe_e", "Integração Contábil · Folha", { situacao: { tipo: "sem_comunicacao", desde: em(-45), cancela_em: em(75) } }),
        ao(em, "exe_f", "Conferência de guias", { situacao: { tipo: "cancelamento_sem_resposta", desde: em(-150), recebido: true } }),
      ] }),
  });
  await abrir(page, "/dashboard");
  const monitores = page.getByTestId("monitor");
  await expect(monitores.nth(0).getByTestId("situacao")).toContainText("Comunicação não está ativa: tentando até");
  await expect(monitores.nth(0).getByTestId("situacao")).toContainText("depois cancela");
  await expect(monitores.nth(1).getByTestId("situacao")).toContainText("Recebeu o cancelamento e não parou em 2 min");
  await expect(monitores.nth(1).getByRole("button", { name: "Parar a execução" })).toHaveCount(0);
  await page.screenshot({ path: `${TELAS}/painel-comunicacao-1920.png`, animations: "disabled" });

  await monitores.nth(1).getByRole("button", { name: "Encerrar no Portal" }).click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("cancelada com erro");
  await expect(dialogo).toContainText("O programa pode ter ficado aberto na máquina");
  await page.screenshot({ path: `${TELAS}/encerrar-no-portal.png`, animations: "disabled" });
  await dialogo.getByRole("button", { name: "Encerrar no Portal" }).click();
  await expect.poll(() => pedidos.filter((p) => p.metodo === "POST" && p.caminho === "/fila/execucoes/exe_f/encerrar")).toHaveLength(1);
  await expect(dialogo).toHaveCount(0);
  expect(erros).toEqual([]);
});
