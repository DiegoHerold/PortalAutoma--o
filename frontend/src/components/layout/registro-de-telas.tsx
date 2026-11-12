"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";

/** A última tela anotada nesta aba: a mesma tela não é anotada duas vezes seguidas. */
let ultima = "";

/**
 * Anota na Auditoria cada tela que a pessoa abre (12/11/2026). Só o caminho, sem a parte depois
 * do "?" (filtros e buscas podem ter dados do cliente). Se falhar, a tela segue normal.
 */
export function RegistroDeTelas() {
  const caminho = usePathname();
  const { token } = useAuth();
  useEffect(() => {
    if (!token || !caminho || caminho === ultima) return;
    ultima = caminho;
    const titulo = typeof document !== "undefined" ? document.title.slice(0, 200) : undefined;
    apiRequest("/governance/auditoria/tela", { token, method: "POST", body: JSON.stringify({ caminho, titulo }) })
      .catch(() => { ultima = ""; });
  }, [caminho, token]);
  return null;
}
