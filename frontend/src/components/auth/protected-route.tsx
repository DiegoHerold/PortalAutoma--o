"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { VOLTAR_PARA } from "@/components/auth/auth-provider";
import { useAuth } from "@/hooks/use-auth";
import { LoadingState } from "@/components/shared/loading-state";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      try {  // volta para cá depois de entrar (ex.: o botão "Continuar processo" do e-mail)
        const aqui = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        if (aqui.startsWith("/") && aqui !== "/" && !aqui.startsWith("/login")) window.sessionStorage.setItem(VOLTAR_PARA, aqui);
      } catch {
        /* sem armazenamento: só vai para o login */
      }
      router.push("/login");
    }
  }, [loading, router, user]);

  if (loading || !user) {
    return <LoadingState label="Validando sessao..." />;
  }

  return <>{children}</>;
}
