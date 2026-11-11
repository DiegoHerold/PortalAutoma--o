import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { API_DE_TESTE } from "../playwright.config";

/*
 * Acompanhar uma execução e acesso por automação (Fase 4). A API é simulada só aqui;
 * as imagens são telas sintéticas geradas para o teste (e2e/fixtures).
 */

const TELAS = "../docs/fase-4-telas";
const IMAGENS: Record<string, Buffer> = {
  img_a: readFileSync(path.join(__dirname, "fixtures", "tela-a.jpg")),
  img_b: readFileSync(path.join(__dirname, "fixtures", "tela-b.jpg")),
};

function acompanhamento(agora: number, pode = true) {
  const em = (s: number) => new Date(agora + s * 1000).toISOString();
  return {
    gerado_em: new Date(agora).toISOString(),
    execucao: { id: "exe_1", status: "running", criada_em: em(-900), iniciada_em: em(-840), concluida_em: null, falha: null, solicitante: "1" },
    automacao: { id: 7, nome: "Integração Contábil · Folha", versao: "2.0.0" },
    pode: { ver_telas_e_logs: pode, controlar: false },
    rodando: true,
    decorrido_s: 840,
    falta_s: 1260,
    termino_previsto: em(1260),
    jobs: [
      { job_id: "job_1", status: "running", pool: "interactive", itens: ["5066"], maquina_id: "mch_1", maquina_nome: "FOLHA-01",
        modo: "direct", tentativa: 1, desde: em(-840), falta_s: 1260, motivo_sem_previsao: null, termino_previsto: em(1260), falha: null },
    ],
    agora: {
      etapa_atual: { etapa: "rubricas", item: "5066", desde: em(-300), tarefas_previstas: 50 },
      item_atual: { item: "5066", rotulo: "Empresa 5066", desde: em(-600) },
      progresso: { atual: 18, total: 50, rotulo: "centro 18 de 50", item: "5066" },
      pausa: null,
      conclusao: null,
      tela: pode
        ? { imagem_id: "img_b", rotulo: "Salvou o centro 18", tipo: "acao", item: "5066", quando: em(-37), desde: em(-37),
            segundos_nesta_tela: 37, espera_rotulo: null, imagem: { situacao: "pronta", motivo: null } }
        : null,
      passos: pode
        ? [
            { id: "p1", rotulo: "Abriu Rubricas", tipo: "abriu", imagem_id: "img_a", item: "5066", quando: em(-300), imagem: { situacao: "pronta", motivo: null } },
            { id: "p2", rotulo: "Filtro sem resultado", tipo: "falha", imagem_id: "img_x", item: "5066", quando: em(-120), imagem: { situacao: "recusada", motivo: "imagem vazia ou de uma cor só" } },
            { id: "p3", rotulo: "Salvou o centro 18", tipo: "acao", imagem_id: "img_b", item: "5066", quando: em(-37), imagem: { situacao: "pronta", motivo: null } },
          ]
        : [],
      atencoes: [{ id: "at1", item: "5081", motivo: "Rubrica 0450 sem conta contábil", quando: em(-200) }],
    },
    estimativa: {
      jobs: [{
        job_id: "job_1",
        etapas: [
          { etapa: "trocar_empresa", nome: "Trocar empresa", item: "5066", estimativa_s: 60, base: { tipo: "item", amostras: 5, texto: "últimas 5 execuções do item" }, motivo: null, motivo_texto: null, situacao: "ok", real_s: 58, tarefas_previstas: null, tarefas_feitas: 0 },
          { etapa: "rubricas", nome: "Rubricas", item: "5066", estimativa_s: 1500, base: { tipo: "item", amostras: 5, texto: "últimas 5 execuções do item" }, motivo: null, motivo_texto: null, situacao: "executando", real_s: null, tarefas_previstas: 50, tarefas_feitas: 18 },
          { etapa: "txt", nome: "Integração (TXT)", item: "5066", estimativa_s: null, base: null, motivo: "sem_historico_etapa", motivo_texto: "rodando pela primeira vez, sem histórico de estimativas", situacao: "pendente", real_s: null, tarefas_previstas: null, tarefas_feitas: 0 },
        ],
      }],
    },
  };
}

const LOGS = [
  { id: "l1", nivel: "info", texto: "Abrindo Rubricas da empresa 5066", item: "5066", espera: false, quando: new Date().toISOString() },
  { id: "l2", nivel: "info", texto: "Centro 17 de 50 conferido", item: "5066", espera: false, quando: new Date().toISOString() },
  { id: "l3", nivel: "aviso", texto: "Rubrica 0450 sem conta contábil: senha=*** removida do log", item: "5081", espera: false, quando: new Date().toISOString() },
  { id: "l4", nivel: "info", texto: "Centro 18 de 50 salvo", item: "5066", espera: false, quando: new Date().toISOString() },
];

type Pedido = { metodo: string; url: string; caminho: string; corpo: unknown };

async function preparar(page: Page, { tema = "light", pode = true }: { tema?: "light" | "dark"; pode?: boolean } = {}) {
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
    pedidos.push({ metodo: req.method(), url: req.url(), caminho, corpo });
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(b) });
    if (caminho === "/auth/me") return json({ id: 1, email: "operador@teste.invalid", name: "Operador de Teste", role: "admin", permissions: [], rbac_permissions: [] });
    if (caminho.endsWith("/avisos")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: pronto\ndata: {}\n\n" });
    if (caminho === "/execucoes/exe_1/acompanhar") return json(acompanhamento(Date.now(), pode));
    if (caminho === "/execucoes/exe_1/logs") return json({ logs: url.searchParams.get("depois") ? [] : LOGS, cursor: "l4" });
    const imagem = caminho.match(/^\/execucoes\/exe_1\/imagens\/(\w+)$/);
    if (imagem) {
      const bytes = IMAGENS[imagem[1]];
      return bytes ? route.fulfill({ status: 200, contentType: "image/jpeg", body: bytes }) : route.fulfill({ status: 404, body: "{}" });
    }
    if (caminho === "/automations/7/acessos" && req.method() === "GET")
      return json({ acoes_possiveis: [], concessoes: [
        { id: "agr_1", user_id: 3, team_id: null, nome: "Pessoa da Folha", email: "folha@teste.invalid", acoes: ["ver_execucoes"], atualizada_em: null },
        { id: "agr_2", user_id: null, team_id: 2, nome: "Fiscal", email: null, acoes: ["ver_execucoes", "ver_telas_e_logs"], atualizada_em: null },
      ] });
    if (caminho === "/automations/7/acessos" && req.method() === "PUT") return json({ concessao: corpo });
    if (caminho === "/users") return json([{ id: 4, name: "Outra Pessoa", email: "outra@teste.invalid", is_active: true, role: { slug: "viewer" } }]);
    if (caminho === "/teams") return json([]);
    return json([]);
  });
  return { pedidos, erros };
}

for (const tema of ["light", "dark"] as const) {
  for (const tela of [
    { nome: "desktop", viewport: { width: 1440, height: 900 } },
    { nome: "celular", viewport: { width: 390, height: 844 } },
  ]) {
    test(`acompanhar ao vivo — ${tela.nome}, tema ${tema === "light" ? "claro" : "escuro"}`, async ({ page }) => {
      await page.setViewportSize(tela.viewport);
      const { pedidos, erros } = await preparar(page, { tema });
      await page.goto("/execucoes/exe_1");
      await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
      await expect(page.getByRole("heading", { name: "Integração Contábil · Folha" })).toBeVisible();
      await expect(page.getByText(/3\d s nesta tela/)).toBeVisible();
      await expect(page.getByTestId("log-ao-vivo")).toContainText("Centro 18 de 50 salvo");
      await expect(page.getByText("Imagem recusada: imagem vazia ou de uma cor só")).toBeVisible();
      await expect(page.locator("img[alt='Salvou o centro 18']").first()).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: `${TELAS}/acompanhar-${tela.nome}-${tema === "light" ? "claro" : "escuro"}.png`, fullPage: true, animations: "disabled" });
      expect(pedidos.filter((p) => /token=/.test(p.url))).toEqual([]);
      expect(pedidos.some((p) => p.caminho === "/execucoes/exe_1/avisos")).toBe(true);
      expect(erros).toEqual([]);
    });
  }
}

test("sem a concessão de telas e logs, a tela não pede log nem imagem", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page, { pode: false });
  await page.goto("/execucoes/exe_1");
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await expect(page.getByText("Telas e logs desta automação são restritos")).toBeVisible();
  await expect(page.getByText("Rubricas").first()).toBeVisible();
  await page.screenshot({ path: `${TELAS}/acompanhar-sem-concessao.png`, fullPage: true, animations: "disabled" });
  expect(pedidos.filter((p) => p.caminho.includes("/logs") || p.caminho.includes("/imagens/"))).toEqual([]);
  expect(erros).toEqual([]);
});

test("ampliar a tela abre a imagem cheia e voltar ao vivo depois de ver um passo antigo", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page);
  await page.goto("/execucoes/exe_1");
  await page.getByRole("button", { name: /Abriu Rubricas/ }).click();
  await expect(page.getByText("Passo anterior")).toBeVisible();
  await page.getByRole("button", { name: "Voltar ao vivo" }).click();
  await expect(page.getByText("Tela agora")).toBeVisible();
  await page.getByRole("button", { name: "Ampliar a tela" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect.poll(() => pedidos.some((p) => p.url.includes("/imagens/img_b?tamanho=cheia"))).toBe(true);
  expect(erros).toEqual([]);
});

test("acesso por automação: marcar telas e logs manda a concessão", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { pedidos, erros } = await preparar(page);
  await page.goto("/automations/7/acessos");
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await expect(page.getByText("Pessoa da Folha")).toBeVisible();
  await page.screenshot({ path: `${TELAS}/acessos-da-automacao.png`, fullPage: true, animations: "disabled" });
  // A caixa mostra o que o servidor confirmou; o clique só pede a mudança.
  await page.getByRole("checkbox", { name: "Ver telas e logs para Pessoa da Folha" }).click();
  await expect
    .poll(() => pedidos.filter((p) => p.metodo === "PUT").map((p) => p.corpo))
    .toEqual([{ user_id: 3, acoes: ["ver_execucoes", "ver_telas_e_logs"] }]);
  expect(erros).toEqual([]);
});
