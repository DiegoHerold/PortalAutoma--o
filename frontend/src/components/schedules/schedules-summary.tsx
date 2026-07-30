"use client";

import { AlertTriangle, CalendarClock, CheckCircle2, Flame, Loader } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/utils";
import type { ScheduleCalendarSummary } from "@/types/schedule";

/**
 * Resumo compacto do período (seção 6) — chips pequenos, não um dashboard separado.
 */
export function SchedulesSummary({ summary }: { summary: ScheduleCalendarSummary | null }) {
  if (!summary) return null;

  const chips: { label: string; icon: typeof CheckCircle2; tone: string }[] = [
    { label: `${summary.total} programados`, icon: CalendarClock, tone: "text-muted-foreground" },
    { label: `${summary.completed} concluídos`, icon: CheckCircle2, tone: "text-success" },
    { label: `${summary.running} em andamento`, icon: Loader, tone: "text-info" },
    { label: `${summary.failed} com falha`, icon: AlertTriangle, tone: "text-destructive" },
    { label: `${summary.future} futuros`, icon: CalendarClock, tone: "text-muted-foreground" },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <span
          key={chip.label}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium"
        >
          <chip.icon className={cn("h-3.5 w-3.5", chip.tone)} aria-hidden />
          {chip.label}
        </span>
      ))}
      {summary.peak_count > 1 && summary.peak_from && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
          <Flame className="h-3.5 w-3.5" aria-hidden />
          Maior concentração: {formatTime(summary.peak_from)}
          {summary.peak_to ? `–${formatTime(summary.peak_to)}` : ""} · {summary.peak_count} simultâneas
        </span>
      )}
    </div>
  );
}
