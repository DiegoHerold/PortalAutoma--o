"use client";

import type { ReactNode } from "react";
import { createContext, useEffect, useMemo, useState } from "react";

import { clearStoredToken, fetchCurrentUser, getStoredToken, login, setStoredToken } from "@/lib/auth";
import type { CurrentUser, LoginInput } from "@/types/auth";

type AuthContextValue = {
  user: CurrentUser | null;
  token: string | null;
  loading: boolean;
  signIn: (input: LoginInput) => Promise<CurrentUser>;
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

  async function signIn(input: LoginInput) {
    const result = await login(input);
    setStoredToken(result.access_token);
    const currentUser = await fetchCurrentUser(result.access_token);
    setToken(result.access_token);
    setUser(currentUser);
    return currentUser;
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
      signOut,
    }),
    [loading, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
