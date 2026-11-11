"use client";

import { ChevronsDown } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ScheduleItemRow } from "@/components/schedules/schedule-calendar-item";
import { Button } from "@/components/ui/button";
import { addDays, dayLabel, isSameDay, toDateKey } from "@/lib/calendar";
import { temporalBucket } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Density } from "@/components/schedules/schedule-calendar-item";
import type { ScheduleCalendarItem } from "@/types/schedule";

/**
 * Visão Agenda (seção 18) — estrutura cronológica Hoje/Amanhã/dia da semana, com
 * Passados/Em andamento/Futuros dentro de cada dia. Lista (não grid), então é também a
 * alternativa acessível ao calendário visual (seção 36).
 */
export function AgendaView({
  from,
  to,
  itemsByDay,
  onSelectItem,
  onLoadMore,
  density = "comfortable",
}: {
  from: Date;
  to: Date;
  itemsByDay: Map<string, ScheduleCalendarItem[]>;
  onSelectItem: (item: ScheduleCalendarItem) => void;
  onLoadMore?: () => void;
  density?: Density;
}) {
  const days: Date[] = [];
  for (let d = from; d <= to; d = addDays(d, 1)) days.push(d);
  const today = new Date();
  const tomorrow = addDays(today, 1);
  const nonEmptyDays = days.filter((d) => (itemsByDay.get(toDateKey(d)) ?? []).length > 0);

  if (nonEmptyDays.length === 0) {
    return <EmptyState title="Nenhum agendamento no período" description="Ajuste os filtros ou navegue para outro intervalo." />;
  }

  return (
    <div className="space-y-4">
      {nonEmptyDays.map((date) => {
        const key = toDateKey(date);
        const items = (itemsByDay.get(key) ?? []).slice().sort((a, b) => a.planned_start.localeCompare(b.planned_start));
        const label = isSameDay(date, today) ? "Hoje" : isSameDay(date, tomorrow) ? "Amanhã" : dayLabel(date);
        const past = items.filter((i) => temporalBucket(i.temporal_status) === "past");
        const present = items.filter((i) => temporalBucket(i.temporal_status) === "present");
        const future = items.filter((i) => temporalBucket(i.temporal_status) === "future");

        return (
          <div key={key} className="overflow-hidden rounded-lg border border-border bg-card">
            <div className={cn("flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2 text-sm font-semibold capitalize", isSameDay(date, today) && "text-primary")}>
              {label}
              <span className="text-xs font-normal text-muted-foreground">{items.length} ocorrência(s)</span>
            </div>
            <AgendaGroup label="Em andamento" items={present} onSelectItem={onSelectItem} density={density} />
            <AgendaGroup label="Passados" items={past} onSelectItem={onSelectItem} density={density} />
            <AgendaGroup label="Futuros" items={future} onSelectItem={onSelectItem} density={density} />
          </div>
        );
      })}

      {onLoadMore && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={onLoadMore}>
            <ChevronsDown className="h-3.5 w-3.5" /> Carregar mais dias
          </Button>
        </div>
      )}
    </div>
  );
}

function AgendaGroup({
  label,
  items,
  onSelectItem,
  density,
}: {
  label: string;
  items: ScheduleCalendarItem[];
  onSelectItem: (item: ScheduleCalendarItem) => void;
  density: Density;
}) {
  if (items.length === 0) return null;
  return (
    <div className="divide-y divide-border/60">
      <p className="bg-muted/10 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      {items.map((item) => (
        <ScheduleItemRow key={item.id} item={item} onClick={() => onSelectItem(item)} density={density} />
      ))}
    </div>
  );
}
