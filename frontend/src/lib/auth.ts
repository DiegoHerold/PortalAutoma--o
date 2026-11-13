import { apiRequest } from "@/lib/api";
import type { CurrentUser, LoginInput, TokenResponse } from "@/types/auth";

const TOKEN_KEY = "portal_token";
/** Navegador confiável (13/11/2026): um por e-mail, neste navegador. Pula o código por 30 dias. */
const DISPOSITIVOS_KEY = "portal_dispositivos";

/** Senha certa: ou já entra (token), ou pede o código mandado por e-mail. */
export type RespostaDoLogin =
  | (TokenResponse & { aviso?: string })
  | { precisa_codigo: true; desafio: string; email: string; codigo_vale_ate: string; tentativas: number };

export async function login(input: LoginInput): Promise<RespostaDoLogin> {
  return apiRequest<RespostaDoLogin>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ ...input, dispositivo: dispositivoDe(input.email) }),
  });
}

export async function confirmarCodigo(desafio: string, codigo: string, confiar: boolean, email: string): Promise<TokenResponse> {
  const r = await apiRequest<TokenResponse & { dispositivo?: string }>("/auth/codigo", {
    method: "POST",
    body: JSON.stringify({ desafio, codigo, confiar }),
  });
  if (r.dispositivo) guardarDispositivo(email, r.dispositivo);
  return r;
}

export function reenviarCodigo(desafio: string) {
  return apiRequest<{ email: string; codigo_vale_ate: string; tentativas: number }>("/auth/codigo/reenviar", {
    method: "POST",
    body: JSON.stringify({ desafio }),
  });
}

export function pedirLinkDeSenha(email: string) {
  return apiRequest<{ mensagem: string }>("/auth/esqueci", { method: "POST", body: JSON.stringify({ email }) });
}

export function verLinkDeSenha(token: string) {
  return apiRequest<{ tipo: "convite" | "redefinir"; email: string; nome: string; vale_ate: string }>("/auth/senha/ver", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function definirSenha(token: string, senha: string) {
  return apiRequest<{ mensagem: string }>("/auth/senha", { method: "POST", body: JSON.stringify({ token, senha }) });
}

export async function fetchCurrentUser(token: string): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/me", { token });
}

function lerDispositivos(): Record<string, string> {
  try {
    const bruto = window.localStorage.getItem(DISPOSITIVOS_KEY);
    const dados = bruto ? (JSON.parse(bruto) as unknown) : {};
    return dados && typeof dados === "object" ? (dados as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function dispositivoDe(email: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  return lerDispositivos()[email.trim().toLowerCase()];
}

function guardarDispositivo(email: string, token: string): void {
  try {
    window.localStorage.setItem(DISPOSITIVOS_KEY, JSON.stringify({ ...lerDispositivos(), [email.trim().toLowerCase()]: token }));
  } catch {
    /* sem armazenamento: na próxima vez pede o código */
  }
}

export function esquecerDispositivo(email: string): void {
  try {
    const dados = lerDispositivos();
    delete dados[email.trim().toLowerCase()];
    window.localStorage.setItem(DISPOSITIVOS_KEY, JSON.stringify(dados));
  } catch {
    /* nada a fazer */
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
