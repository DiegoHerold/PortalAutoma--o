"use client";

import { Children, useState, type ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Regra do design system: só a busca à mostra; o resto dos filtros atrás de "Filtros".
 * O primeiro filho é a busca; os demais aparecem ao abrir, na grade de ``className``.
 */
export function FiltrosEscondidos({ className, ativos = 0, children }: { className?: string; ativos?: number; children: ReactNode }) {
  const [aberto, setAberto] = useState(false);
  const [busca, ...resto] = Children.toArray(children);
  return (
    <div className="flex flex-1 flex-wrap items-end gap-3">
      <div className="min-w-[14rem] max-w-md flex-1">{busca}</div>
      {resto.length > 0 && (
        <Button variant="outline" onClick={() => setAberto((v) => !v)} aria-expanded={aberto}>
          <SlidersHorizontal className="h-4 w-4" /> Filtros{ativos ? ` (${ativos})` : ""}
        </Button>
      )}
      {aberto && resto.length > 0 && <div className={cn("grid basis-full gap-3", className)}>{resto}</div>}
    </div>
  );
}
