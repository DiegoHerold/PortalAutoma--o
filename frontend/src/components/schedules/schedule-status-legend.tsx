"use client";

import { useState } from "react";
import { Bot, ChevronDown, Workflow } from "lucide-react";

import { TEMPORAL_STATUS } from "@/lib/status";
import { cn } from "@/lib/utils";

const STATUS_ORDER = Object.entries(TEMPORAL_STATUS).sort((a, b) => (a[1].order ?? 99) - (b[1].order ?? 99));

/** Legenda discreta e recolhível (seção 10) — não depende só de cor: ícone + badge + texto. */
export function ScheduleStatusLegend() {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-card text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 font-medium text-muted-foreground hover:text-foreground"
        aria-expanded={open}
      >
        Legenda
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-3">
          <div>
            <p className="mb-1.5 font-semibold uppercase tracking-wide text-muted-foreground">Tipo</p>
            <div className="flex flex-wrap gap-3">
              <span className="flex items-center gap-1.5">
                <Bot className="h-3.5 w-3.5" aria-hidden /> Automação
              </span>
              <span className="flex items-center gap-1.5">
                <Workflow className="h-3.5 w-3.5" aria-hidden /> Fluxo
              </span>
            </div>
          </div>
          <div>
            <p className="mb-1.5 font-semibold uppercase tracking-wide text-muted-foreground">Estado</p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {STATUS_ORDER.map(([key, meta]) => {
                const Icon = meta.icon;
                return (
                  <span key={key} className="flex items-start gap-1.5" title={meta.description}>
                    <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span>
                      <span className="block font-medium text-foreground">{meta.label}</span>
                      {meta.description && <span className="block text-xs text-muted-foreground">{meta.description}</span>}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
