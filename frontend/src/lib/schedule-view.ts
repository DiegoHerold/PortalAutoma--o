import { addDays, addMonths, addWeeks, dayLabel, getMonthGridDays, getWeekDays, monthLabel, rangeLabel, weekRangeLabel } from "@/lib/calendar";

/** As 5 visões da Central de Agendamentos (seção 2). "Agora" é um recorte operacional, não navegável por data. */
export const SCHEDULE_VIEWS = ["now", "day", "week", "month", "agenda"] as const;
export type ScheduleView = (typeof SCHEDULE_VIEWS)[number];

export function parseScheduleView(value: string | null): ScheduleView {
  return (SCHEDULE_VIEWS as readonly string[]).includes(value ?? "") ? (value as ScheduleView) : "week";
}

const AGENDA_SPAN_DAYS = 13;

/**
 * O backend só aceita `from`/`to` como datas de dia inteiro (não datetime — ver
 * calendar.py::build_schedule_calendar), então "Agora" busca hoje + amanhã (cobre itens que
 * atravessam a meia-noite) e o recorte fino por horário acontece no cliente
 * (schedules-now-view.tsx), usando o `temporal_status` já calculado pelo servidor.
 */
export function scheduleViewRange(view: ScheduleView, anchor: Date, now: Date = new Date()): { from: Date; to: Date } {
  switch (view) {
    case "now": {
      const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      return { from: startOfToday, to: addDays(startOfToday, 1) };
    }
    case "day":
      return { from: anchor, to: anchor };
    case "week": {
      const days = getWeekDays(anchor);
      return { from: days[0], to: days[6] };
    }
    case "agenda":
      return { from: anchor, to: addDays(anchor, AGENDA_SPAN_DAYS) };
    default: {
      const gridDays = getMonthGridDays(anchor);
      return { from: gridDays[0].date, to: gridDays[gridDays.length - 1].date };
    }
  }
}

export function scheduleViewHeaderLabel(view: ScheduleView, anchor: Date): string {
  switch (view) {
    case "now":
      return "Agora";
    case "week":
      return weekRangeLabel(getWeekDays(anchor));
    case "day":
      return dayLabel(anchor);
    case "agenda":
      return rangeLabel(anchor, addDays(anchor, AGENDA_SPAN_DAYS));
    default:
      return monthLabel(anchor);
  }
}

export function stepScheduleAnchor(view: ScheduleView, anchor: Date, delta: number): Date {
  switch (view) {
    case "week":
      return addWeeks(anchor, delta);
    case "day":
      return addDays(anchor, delta);
    case "agenda":
      return addDays(anchor, delta * (AGENDA_SPAN_DAYS + 1));
    default:
      return addMonths(anchor, delta);
  }
}

/** Tamanho do bucket de densidade que o backend usa por view — mantido em paridade com calendar.py::bucket_seconds_for_view. */
export function densityBucketSecondsForView(view: ScheduleView): number {
  if (view === "day" || view === "now") return 1800;
  if (view === "week") return 3600;
  return 86400;
}
