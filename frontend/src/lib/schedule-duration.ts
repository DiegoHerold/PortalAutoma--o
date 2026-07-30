import { formatDuration, formatTime } from "@/lib/utils";
import type { ScheduleCalendarItem } from "@/types/schedule";

/**
 * Regras de exibição de duração (Fase 7, seção 21): nunca mostrar um horário final exato
 * quando ele é apenas estimado a partir do histórico. `is_estimated`/`estimated_duration_seconds`
 * vêm prontos do backend (backend/.../scheduling/application/calendar.py::_load_duration_estimates).
 */

export function confidenceLabel(confidence?: ScheduleCalendarItem["estimation_confidence"]): string {
  switch (confidence) {
    case "high":
      return "média de várias execuções recentes";
    case "medium":
      return "média de algumas execuções recentes";
    case "low":
      return "baseado em poucas execuções — pouca confiança";
    default:
      return "";
  }
}

/** "Concluído em 18 min" | "Em andamento há 6 min" | "Duração média: aprox. 25 min" | "Duração não estimada". */
export function durationSummary(item: ScheduleCalendarItem, nowMs: number = Date.now()): string {
  if (item.duration_seconds != null) {
    return `${formatDuration(item.duration_seconds)}`;
  }
  if (item.actual_start && !item.actual_end) {
    const elapsed = (nowMs - new Date(item.actual_start).getTime()) / 1000;
    return `em andamento há ${formatDuration(elapsed)}`;
  }
  if (item.is_estimated && item.estimated_duration_seconds != null) {
    return `aprox. ${formatDuration(item.estimated_duration_seconds)} (estimado)`;
  }
  return "duração não estimada";
}

/** "Planejado 08:00" ou, quando há estimativa, "Planejado 08:00 · término estimado aprox. 10:00". */
export function plannedRangeLabel(item: ScheduleCalendarItem): string {
  const start = formatTime(item.planned_start);
  if (item.actual_end) {
    return `${start} – ${formatTime(item.actual_end)}`;
  }
  if (item.is_estimated && item.effective_end) {
    return `${start} – aprox. ${formatTime(item.effective_end)}`;
  }
  return start;
}

/** Janela [start, end) usada para layout (lanes, densidade) — nunca de largura zero. */
export function effectiveWindow(item: ScheduleCalendarItem): { start: Date; end: Date } {
  const start = new Date(item.actual_start ?? item.planned_start);
  const rawEnd = item.actual_end ?? item.effective_end ?? item.planned_start;
  let end = new Date(rawEnd);
  if (end.getTime() <= start.getTime()) {
    end = new Date(start.getTime() + 15 * 60 * 1000);
  }
  return { start, end };
}

export function crossesMidnight(item: ScheduleCalendarItem): boolean {
  const { start, end } = effectiveWindow(item);
  return start.toDateString() !== end.toDateString();
}
