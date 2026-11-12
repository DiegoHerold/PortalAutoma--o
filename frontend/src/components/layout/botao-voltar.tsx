"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ALL_NAV_ITEMS } from "@/lib/navigation";

const PRIMEIRA = "portal.voltar.primeira";

/** Tela "mãe" quando não há para onde voltar (link aberto direto ou numa aba nova). */
const MAE: Record<string, string> = {
  "/execucoes": "/historico",
  "/flow-executions": "/executions",
};

export function telaMae(caminho: string): string {
  const partes = caminho.split("/").filter(Boolean);
  for (let n = partes.length - 1; n > 0; n -= 1) {
    const acima = `/${partes.slice(0, n).join("/")}`;
    if (MAE[acima]) return MAE[acima];
    if (ALL_NAV_ITEMS.some((i) => i.href === acima) || /^\/automations\/[^/]+$/.test(acima)) return acima;
  }
  return "/dashboard";
}

/** Página do menu não tem "Voltar"; qualquer tela de dentro dela tem. */
export function ehTelaDeDentro(caminho: string): boolean {
  return caminho !== "/" && !ALL_NAV_ITEMS.some((i) => i.href === caminho);
}

/**
 * "← Voltar" no topo das telas de dentro (uma automação, uma execução, um job...). Volta para
 * onde a pessoa estava; se ela abriu o link direto, vai para a tela mãe.
 */
export function BotaoVoltar() {
  const caminho = usePathname() ?? "/";
  const router = useRouter();

  useEffect(() => {
    // A primeira tela aberta nesta aba: dela não há "voltar" dentro do Portal.
    try {
      if (!window.sessionStorage.getItem(PRIMEIRA)) window.sessionStorage.setItem(PRIMEIRA, window.location.pathname);
    } catch {
      /* sem armazenamento: vai para a tela mãe */
    }
  }, []);

  if (!ehTelaDeDentro(caminho)) return null;

  function voltar() {
    let primeira: string | null = null;
    try {
      primeira = window.sessionStorage.getItem(PRIMEIRA);
    } catch {
      primeira = null;
    }
    if (primeira && primeira !== caminho && window.history.length > 1) router.back();
    else router.push(telaMae(caminho));
  }

  return (
    <button onClick={voltar} data-testid="botao-voltar"
      className="-mb-2 inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-base font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
      <ArrowLeft className="h-5 w-5" /> Voltar
    </button>
  );
}
