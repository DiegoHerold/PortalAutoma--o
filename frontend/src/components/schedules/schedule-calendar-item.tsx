"use client";

import { Bot, User, Workflow, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { durationSummary, plannedRangeLabel } from "@/lib/schedule-duration";
import { temporalStatusMeta } from "@/lib/status";
import { formatTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { ScheduleCalendarItem } from "@/types/schedule";

export type Density = "comfortable" | "compact";

export function targetIcon(targetType: string): LucideIcon {
  return targetType === "flow" ? Workflow : Bot;
}

/** "[Fluxo]" / "[Automação]" — combinado com o ícone para não depender só de cor (seção 27). */
export function targetLabel(targetType: string): string {
  return targetType === "flow" ? "Fluxo" : "Automação";
}

function progressLabel(item: ScheduleCalendarItem): string | null {
  if (!item.progress || item.progress.total === 0) return null;
  const { succeeded, total, running } = item.progress;
  if (running > 0) return `${succeeded}/${total} nós · ${running} em execução`;
  return `${succeeded}/${total} nós`;
}

/** Pill de uma linha — usado nas células do mês e em colunas estreitas da semana. */
export function ScheduleItemPill({
  item,
  onClick,
}: {
  item: ScheduleCalendarItem;
  onClick: () => void;
}) {
  const meta = temporalStatusMeta(item.temporal_status);
  const Icon = targetIcon(item.target_type);
  const name = item.schedule_name || item.target_name;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={`${name} — ${meta.label}`}
      className={cn(
        "flex w-full items-center gap-1 truncate rounded px-1 py-0.5 text-left text-xs font-medium transition-opacity hover:opacity-80",
        meta.tone === "success" && "bg-success/12 text-success",
        meta.tone === "destructive" && "bg-destructive/12 text-destructive",
        meta.tone === "info" && "bg-info/12 text-info",
        meta.tone === "warning" && "bg-warning/15 text-warning",
        (meta.tone === "neutral" || meta.tone === "outline") && "bg-muted text-muted-foreground",
      )}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      <span className="truncate">
        {formatTime(item.planned_start)} {name}
      </span>
      <span className={cn("ml-auto h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} aria-hidden />
    </button>
  );
}

/** Bloco absoluto-posicionado para as visões Semana/Dia (dentro de uma coluna de horário). */
export function ScheduleItemBlock({
  item,
  onClick,
  compact,
}: {
  item: ScheduleCalendarItem;
  onClick: () => void;
  compact?: boolean;
}) {
  const meta = temporalStatusMeta(item.temporal_status);
  const Icon = targetIcon(item.target_type);
  const name = item.schedule_name || item.target_name;
  const progress = progressLabel(item);

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={`${name} — ${meta.label}`}
      className={cn(
        "flex h-full w-full flex-col overflow-hidden rounded-md border px-1.5 py-1 text-left text-xs leading-tight shadow-sm transition-colors hover:brightness-95",
        meta.tone === "success" && "border-success/30 bg-success/10 text-success",
        meta.tone === "destructive" && "border-destructive/30 bg-destructive/10 text-destructive",
        meta.tone === "info" && "border-info/30 bg-info/10 text-info",
        meta.tone === "warning" && "border-warning/40 bg-warning/10 text-warning",
        (meta.tone === "neutral" || meta.tone === "outline") && "border-border bg-muted text-muted-foreground",
      )}
    >
      <span className="flex items-center gap-1 font-semibold">
        <Icon className="h-3 w-3 shrink-0" aria-hidden />
        <span className="truncate">{name}</span>
      </span>
      {!compact && <span className="truncate text-xs opacity-80">{meta.label}</span>}
      {!compact && progress && <span className="truncate text-xs opacity-80">{progress}</span>}
    </button>
  );
}

/** Linha horizontal — usada em Agenda e na visão Agora. */
export function ScheduleItemRow({
  item,
  onClick,
  density = "comfortable",
}: {
  item: ScheduleCalendarItem;
  onClick: () => void;
  density?: Density;
}) {
  const meta = temporalStatusMeta(item.temporal_status);
  const Icon = targetIcon(item.target_type);
  const name = item.schedule_name || item.target_name;
  const progress = progressLabel(item);
  const StatusIcon = meta.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-accent/40"
    >
      <span className="tabular w-24 shrink-0 text-xs text-muted-foreground">{plannedRangeLabel(item)}</span>
      <span className="flex min-w-0 flex-1 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="min-w-0">
          <span className="block truncate font-medium">{name}</span>
          {density === "comfortable" && (
            <span className="block truncate text-xs text-muted-foreground">
              {targetLabel(item.target_type)}
              {progress ? ` · ${progress}` : ` · ${durationSummary(item)}`}
              {item.responsible && (
                <span className="ml-1 inline-flex items-center gap-0.5">
                  <User className="h-3 w-3" aria-hidden /> {item.responsible}
                </span>
              )}
            </span>
          )}
        </span>
      </span>
      {item.reason && density === "comfortable" && (
        <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">{item.reason}</span>
      )}
      <Badge tone={meta.tone} className="shrink-0 gap-1">
        <StatusIcon className="h-3 w-3" aria-hidden /> {meta.label}
      </Badge>
    </button>
  );
}
