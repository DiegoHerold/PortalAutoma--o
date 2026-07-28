import { apiRequest } from "@/lib/api";
import type { CurrentUser, LoginInput, TokenResponse } from "@/types/auth";

const TOKEN_KEY = "portal_token";

export async function login(input: LoginInput): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function fetchCurrentUser(token: string): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/me", { token });
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
