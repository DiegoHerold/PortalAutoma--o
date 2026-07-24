import type { Schedule } from "@/types/schedule";

const WEEKDAY_NAMES = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];

/** Friendly pt-BR description built from a Schedule's structured recurrence fields (preferred over describeCron). */
export function describeRecurrence(schedule: Pick<Schedule, "recurrence_type" | "time_of_day" | "weekdays" | "day_of_month" | "specific_date">): string {
  const time = schedule.time_of_day || "00:00";
  switch (schedule.recurrence_type) {
    case "daily":
      return `Todo dia às ${time}`;
    case "weekly": {
      const days = (schedule.weekdays ?? []).slice().sort().map((d) => WEEKDAY_NAMES[d] ?? d);
      return days.length ? `${days.join(", ")} às ${time}` : `Semanalmente às ${time}`;
    }
    case "monthly": {
      const day = schedule.day_of_month;
      const dayLabel = day === 0 ? "último dia do mês" : `dia ${day}`;
      return `Todo ${dayLabel} às ${time}`;
    }
    case "once": {
      if (!schedule.specific_date) return `Uma vez às ${time}`;
      const [y, m, d] = schedule.specific_date.split("-");
      return `${d}/${m}/${y} às ${time}`;
    }
    default:
      return time;
  }
}

/** Very small, friendly cron descriptor for common patterns (pt-BR). */
export function describeCron(expr?: string | null): string {
  if (!expr) return "—";
  const parts = expr.trim().split(/\s+/);
  if (parts.length < 5) return expr;
  const [min, hour, dom, mon, dow] = parts;

  const every = (v: string) => v === "*";
  const time = (h: string, m: string) =>
    `${h.padStart(2, "0")}:${m.padStart(2, "0")}`;

  if (every(dom) && every(mon) && every(dow) && !every(hour) && !every(min)) {
    return `Todos os dias às ${time(hour, min)}`;
  }
  if (every(dom) && every(mon) && !every(dow) && !every(hour)) {
    const days = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
    const label = dow.split(",").map((d) => days[Number(d) % 7] ?? d).join(", ");
    return `Toda ${label} às ${time(hour, min)}`;
  }
  if (min.startsWith("*/")) {
    return `A cada ${min.slice(2)} min`;
  }
  if (every(hour) && !every(min)) {
    return `Todo hora no min ${min}`;
  }
  return expr;
}
