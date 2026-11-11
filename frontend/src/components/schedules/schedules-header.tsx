"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Filter, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, type TabItem } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { ScheduleView } from "@/lib/schedule-view";

const VIEW_TABS: TabItem[] = [
  { value: "now", label: "Agora" },
  { value: "day", label: "Dia" },
  { value: "week", label: "Semana" },
  { value: "month", label: "Mês" },
  { value: "agenda", label: "Agenda" },
];

/** Cabeçalho operacional da Central de Agendamentos (seção 5). */
export function SchedulesHeader({
  view,
  onViewChange,
  headerLabel,
  showDateNav,
  onPrev,
  onNext,
  onToday,
  search,
  onSearchChange,
  timezone,
  activeFilterCount,
  onOpenFilters,
  onCreate,
  canCreate,
}: {
  view: ScheduleView;
  onViewChange: (view: ScheduleView) => void;
  headerLabel: string;
  showDateNav: boolean;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  search: string;
  onSearchChange: (value: string) => void;
  timezone: string;
  activeFilterCount: number;
  onOpenFilters: () => void;
  onCreate: () => void;
  canCreate: boolean;
}) {
  const [searchDraft, setSearchDraft] = useState(search);

  useEffect(() => setSearchDraft(search), [search]);

  useEffect(() => {
    const id = setTimeout(() => {
      if (searchDraft !== search) onSearchChange(searchDraft);
    }, 350);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="overflow-x-auto">
            <Tabs value={view} onValueChange={(v) => onViewChange(v as ScheduleView)} items={VIEW_TABS} />
          </div>
          {showDateNav && (
            <div className="flex items-center gap-1.5">
              <Button size="icon" variant="outline" onClick={onPrev} aria-label="Período anterior">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <h2 className={cn("min-w-[9rem] text-center font-display text-sm font-semibold capitalize")}>{headerLabel}</h2>
              <Button size="icon" variant="outline" onClick={onNext} aria-label="Próximo período">
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={onToday}>
                Hoje
              </Button>
            </div>
          )}
          <span className="rounded-full border border-border bg-muted/50 px-2 py-0.5 text-xs font-medium text-muted-foreground" title="Timezone de exibição">
            {timezone}
          </span>
        </div>
        <Button onClick={onCreate} disabled={!canCreate} title={canCreate ? undefined : "Sem permissão para criar agendamentos"}>
          <Plus className="h-4 w-4" /> Criar agendamento
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="Buscar agendamento, automação, fluxo, responsável..."
            className="h-9 pl-8 text-xs"
          />
        </div>
        <Button variant="outline" size="sm" onClick={onOpenFilters}>
          <Filter className="h-3.5 w-3.5" /> Filtros
          {activeFilterCount > 0 && (
            <span className="tabular ml-0.5 rounded-full bg-primary/15 px-1.5 text-xs text-primary">{activeFilterCount}</span>
          )}
        </Button>
      </div>
    </div>
  );
}
