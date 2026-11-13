"use client";

import type { ReactNode } from "react";
import { createContext, useEffect, useMemo, useState } from "react";

import { SESSAO_EXPIRADA } from "@/lib/api";
import { clearStoredToken, fetchCurrentUser, getStoredToken, login, setStoredToken } from "@/lib/auth";

/** Para onde voltar depois de entrar de novo, e o aviso de sessão vencida (sessionStorage). */
export const VOLTAR_PARA = "portal.voltar_para";
export const AVISO_SESSAO = "portal.sessao_expirada";
import type { CurrentUser, LoginInput } from "@/types/auth";

type AuthContextValue = {
  user: CurrentUser | null;
  token: string | null;
  loading: boolean;
  signIn: (input: LoginInput) => Promise<CurrentUser>;
  /** Fim do login em dois passos (13/11/2026): guarda o token e carrega a pessoa. */
  concluirLogin: (accessToken: string) => Promise<CurrentUser>;
  signOut: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedToken = getStoredToken();
    if (!storedToken) {
      setLoading(false);
      return;
    }

    fetchCurrentUser(storedToken)
      .then((currentUser) => {
        setToken(storedToken);
        setUser(currentUser);
      })
      .catch(() => {
        clearStoredToken();
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  // Qualquer pedido que volte 401 com token: a sessão venceu. Guarda onde a pessoa estava e sai.
  useEffect(() => {
    function expirou() {
      try {
        const aqui = `${window.location.pathname}${window.location.search}`;
        if (aqui.startsWith("/") && !aqui.startsWith("/login")) window.sessionStorage.setItem(VOLTAR_PARA, aqui);
        window.sessionStorage.setItem(AVISO_SESSAO, "1");
      } catch {
        /* sem armazenamento: só sai */
      }
      clearStoredToken();
      setToken(null);
      setUser(null);
    }
    window.addEventListener(SESSAO_EXPIRADA, expirou);
    return () => window.removeEventListener(SESSAO_EXPIRADA, expirou);
  }, []);

  async function concluirLogin(accessToken: string) {
    setStoredToken(accessToken);
    const currentUser = await fetchCurrentUser(accessToken);
    setToken(accessToken);
    setUser(currentUser);
    return currentUser;
  }

  /** Só para quando não há código (envio de e-mail desligado); a tela de login usa o passo a passo. */
  async function signIn(input: LoginInput) {
    const result = await login(input);
    if (!("access_token" in result)) throw new Error("Este login pede o código enviado por e-mail.");
    return concluirLogin(result.access_token);
  }

  function signOut() {
    clearStoredToken();
    setToken(null);
    setUser(null);
  }

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      signIn,
      concluirLogin,
      signOut,
    }),
    [loading, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
