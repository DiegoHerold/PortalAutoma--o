"use client";

import { AlertTriangle, Bot, CalendarClock, LayoutGrid, Loader, Workflow } from "lucide-react";

import { cn } from "@/lib/utils";
import type { TargetType } from "@/types/schedule";

export type QuickFilterState = {
  targetType: TargetType | "all";
  statuses: string[];
};

const CHIPS: { key: string; label: string; icon: typeof Bot }[] = [
  { key: "all", label: "Todos", icon: LayoutGrid },
  { key: "automation", label: "Automações", icon: Bot },
  { key: "flow", label: "Fluxos", icon: Workflow },
  { key: "running", label: "Em andamento", icon: Loader },
  { key: "failed", label: "Com falha", icon: AlertTriangle },
  { key: "future", label: "Futuros", icon: CalendarClock },
];

function isActive(key: string, state: QuickFilterState): boolean {
  if (key === "all") return state.targetType === "all" && state.statuses.length === 0;
  if (key === "automation" || key === "flow") return state.targetType === key;
  return state.statuses.includes(key);
}

/**
 * Nível 1 — filtros rápidos, sempre visíveis e compactos (seção 7). Não abrem painel,
 * não ocupam espaço do calendário: são chips clicáveis que ligam direto nos parâmetros da URL.
 */
export function SchedulesFilterBar({
  state,
  onChange,
}: {
  state: QuickFilterState;
  onChange: (next: QuickFilterState) => void;
}) {
  function toggle(key: string) {
    if (key === "all") {
      onChange({ targetType: "all", statuses: [] });
      return;
    }
    if (key === "automation" || key === "flow") {
      onChange({ ...state, targetType: state.targetType === key ? "all" : (key as TargetType) });
      return;
    }
    const has = state.statuses.includes(key);
    onChange({ ...state, statuses: has ? state.statuses.filter((s) => s !== key) : [...state.statuses, key] });
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filtros rápidos">
      {CHIPS.map((chip) => {
        const active = isActive(chip.key, state);
        return (
          <button
            key={chip.key}
            type="button"
            onClick={() => toggle(chip.key)}
            aria-pressed={active}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
              active ? "border-primary/40 bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground hover:text-foreground",
            )}
          >
            <chip.icon className="h-3.5 w-3.5" aria-hidden />
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
