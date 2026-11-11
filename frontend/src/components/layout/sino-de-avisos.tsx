"use client";

import { useState } from "react";
import Link from "next/link";
import { Bell, CheckCheck, Settings } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { horario } from "@/lib/fila";
import type { Avisos } from "@/lib/notificacoes";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/** Sino no topo: os avisos da pessoa (erro, atenção, máquina, fila, término). Relê a cada minuto. */
export function SinoDeAvisos() {
  const { token } = useAuth();
  const [aberto, setAberto] = useState(false);
  const avisos = useApi<Avisos>("/notificacoes?limite=20", { pollMs: 60000 });
  const naoLidas = typeof avisos.data?.nao_lidas === "number" ? avisos.data.nao_lidas : 0;
  const lista = Array.isArray(avisos.data?.avisos) ? avisos.data.avisos : [];

  async function marcarLidas(ids?: string[]) {
    await apiRequest("/notificacoes/lidas", { method: "POST", token, body: JSON.stringify(ids ? { ids } : {}) });
    await avisos.refetch();
  }

  return (
    <div className="relative">
      <Button variant="ghost" size="icon" onClick={() => setAberto((v) => !v)} aria-expanded={aberto}
        aria-label={naoLidas ? `Avisos: ${naoLidas} por ler` : "Avisos"} className="relative">
        <Bell className="h-5 w-5" />
        {naoLidas > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded-full bg-destructive px-1 text-[0.7rem] font-bold leading-none text-white" data-testid="avisos-por-ler">
            {naoLidas > 99 ? "99+" : naoLidas}
          </span>
        )}
      </Button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setAberto(false)} />
          <div className="absolute right-0 top-11 z-20 w-[22rem] max-w-[calc(100vw-2rem)] animate-fade-in overflow-hidden rounded-xl border border-border bg-popover shadow-lg" role="dialog" aria-label="Avisos">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <p className="titulo-condensado text-lg">Avisos</p>
              <div className="flex items-center gap-1">
                {naoLidas > 0 && (
                  <Button variant="ghost" size="sm" onClick={() => void marcarLidas()}>
                    <CheckCheck className="h-4 w-4" /> Marcar todos como lidos
                  </Button>
                )}
                <Link href="/settings#notificacoes" onClick={() => setAberto(false)} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted" aria-label="Escolher o que receber" title="Escolher o que receber">
                  <Settings className="h-4 w-4" />
                </Link>
              </div>
            </div>
            <ul className="max-h-[26rem] divide-y divide-border overflow-y-auto">
              {lista.length === 0 && (
                <li className="px-4 py-8 text-center text-sm text-muted-foreground">
                  Nenhum aviso. Escolha o que receber em <Link href="/settings#notificacoes" className="font-medium text-primary underline-offset-2 hover:underline" onClick={() => setAberto(false)}>Configurações</Link>.
                </li>
              )}
              {lista.map((a) => (
                <li key={a.id} className={cn("px-4 py-3", !a.lida && "bg-primary/5")}>
                  <Link href={a.link ?? "#"} onClick={() => { setAberto(false); if (!a.lida) void marcarLidas([a.id]); }} className="block">
                    <p className="flex items-start gap-2 font-medium text-titulo">
                      {!a.lida && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-destructive" aria-label="por ler" />}
                      <span>{a.titulo}</span>
                    </p>
                    <p className="mt-0.5 text-sm text-muted-foreground">{a.texto}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{horario(a.quando)}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
