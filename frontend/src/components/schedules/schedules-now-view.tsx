"use client";

import { AlarmClock, CheckCircle2, Clock3, Hourglass, Loader } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ScheduleItemRow } from "@/components/schedules/schedule-calendar-item";
import type { ScheduleCalendarItem } from "@/types/schedule";

type Bucket = { key: string; title: string; icon: typeof Loader; items: ScheduleCalendarItem[]; emphasis?: boolean };

/**
 * Visão "Agora" (seção 14) — recorte operacional dedicado ao momento atual. Não substitui a
 * página geral de Execuções; é só um recorte temporal dentro de Agendamentos.
 */
export function SchedulesNowView({
  items,
  onSelect,
}: {
  items: ScheduleCalendarItem[];
  onSelect: (item: ScheduleCalendarItem) => void;
}) {
  const running = items.filter((i) => ["running", "cancelling", "preparing"].includes(i.temporal_status)).sort((a, b) => (a.actual_start ?? a.planned_start).localeCompare(b.actual_start ?? b.planned_start));
  const awaiting = items.filter((i) => i.temporal_status === "awaiting_trigger");
  const delayed = items.filter((i) => i.temporal_status === "delayed");
  const recentlyDone = items
    .filter((i) => i.temporal_status.startsWith("past_") && i.actual_end)
    .sort((a, b) => (b.actual_end ?? "").localeCompare(a.actual_end ?? ""))
    .slice(0, 10);
  const upcoming = items
    .filter((i) => i.temporal_status.startsWith("future_"))
    .sort((a, b) => a.planned_start.localeCompare(b.planned_start))
    .slice(0, 12);

  const buckets: Bucket[] = [
    { key: "running", title: `${running.length} em andamento`, icon: Loader, items: running, emphasis: true },
    { key: "awaiting", title: `${awaiting.length} aguardando início`, icon: Hourglass, items: awaiting },
    { key: "delayed", title: `${delayed.length} atrasado${delayed.length === 1 ? "" : "s"}`, icon: AlarmClock, items: delayed, emphasis: delayed.length > 0 },
    { key: "recent", title: `${recentlyDone.length} concluídos recentemente`, icon: CheckCircle2, items: recentlyDone },
    { key: "upcoming", title: `${upcoming.length} próximos`, icon: Clock3, items: upcoming },
  ];

  const total = items.length;
  if (total === 0) {
    return <EmptyState title="Nenhuma execução em andamento" description="Nada rodando, atrasado ou previsto para as próximas horas." />;
  }

  return (
    <div className="space-y-4">
      {buckets.map((bucket) =>
        bucket.items.length === 0 ? null : (
          <section key={bucket.key} className="overflow-hidden rounded-lg border border-border bg-card">
            <div
              className={
                "flex items-center gap-2 border-b border-border px-4 py-2.5 text-sm font-semibold " +
                (bucket.emphasis ? "bg-warning/10 text-warning" : "bg-muted/30")
              }
            >
              <bucket.icon className="h-4 w-4" aria-hidden />
              {bucket.title}
            </div>
            <div className="divide-y divide-border/60">
              {bucket.items.map((item) => (
                <ScheduleItemRow key={item.id} item={item} onClick={() => onSelect(item)} />
              ))}
            </div>
          </section>
        ),
      )}
    </div>
  );
}
