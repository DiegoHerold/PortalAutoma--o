import { defineConfig, devices } from "@playwright/test";

/**
 * Testes de tela. A API é simulada dentro de cada teste (page.route) apontando o
 * frontend para um host que não existe; nenhum dado simulado vai para a aplicação.
 */
const PORTA = 3107;
export const API_DE_TESTE = "http://api.teste.invalid/api/v1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORTA}`,
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: `npx next dev --turbopack -p ${PORTA} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORTA}/login`,
    timeout: 240_000,
    reuseExistingServer: false,
    // Pasta própria: nunca tocar no `.next` do build de produção do portal.
    env: { NEXT_PUBLIC_API_URL: API_DE_TESTE, NEXT_DIST_DIR: ".next-e2e", NEXT_TSCONFIG: "tsconfig.e2e.json" },
  },
});
