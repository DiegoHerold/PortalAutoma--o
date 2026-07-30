const MONTH_LABELS = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

const WEEKDAY_SHORT_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

/** "YYYY-MM-DD" in local time (never UTC -- avoids off-by-one-day bugs near midnight). */
export function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Inverso de toDateKey — parseia "YYYY-MM-DD" como data local (evita off-by-one perto da meia-noite). */
export function parseDateKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y || 1970, (m || 1) - 1, d || 1);
}

export function monthLabel(date: Date): string {
  return `${MONTH_LABELS[date.getMonth()]} de ${date.getFullYear()}`;
}

export const WEEKDAY_HEADER_LABELS = WEEKDAY_SHORT_LABELS;

/**
 * Full set of calendar cells for the month containing `anchor`, padded with
 * the trailing days of the previous month and the leading days of the next
 * month so every row is a complete Mon-Sun week. Always 5 or 6 rows (35 or
 * 42 cells) depending on how the month falls.
 */
export function getMonthGridDays(anchor: Date): { date: Date; inMonth: boolean }[] {
  const year = anchor.getFullYear();
  const month = anchor.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const lastOfMonth = new Date(year, month + 1, 0);

  // JS getDay(): 0=Sun..6=Sat. Convert to Mon-start offset (0=Mon..6=Sun).
  const leadingOffset = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - leadingOffset);

  const totalDaysShown = Math.ceil((leadingOffset + lastOfMonth.getDate()) / 7) * 7;

  const days: { date: Date; inMonth: boolean }[] = [];
  for (let i = 0; i < totalDaysShown; i++) {
    const d = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
    days.push({ date: d, inMonth: d.getMonth() === month });
  }
  return days;
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function addMonths(date: Date, delta: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

export function addDays(date: Date, delta: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + delta);
}

export function addWeeks(date: Date, delta: number): Date {
  return addDays(date, delta * 7);
}

/** Segunda-feira da semana que contém `anchor` (semana Seg-Dom, mesma convenção do grid mensal). */
export function startOfWeek(anchor: Date): Date {
  const offset = (anchor.getDay() + 6) % 7; // 0=Mon..6=Sun
  return addDays(anchor, -offset);
}

/** Os 7 dias (Seg-Dom) da semana que contém `anchor`. */
export function getWeekDays(anchor: Date): Date[] {
  const start = startOfWeek(anchor);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

const WEEKDAY_LONG_LABELS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"];

/** "Quarta-feira, 29 de julho de 2026" */
export function dayLabel(date: Date): string {
  const weekday = WEEKDAY_LONG_LABELS[(date.getDay() + 6) % 7];
  return `${weekday}, ${date.getDate()} de ${MONTH_LABELS[date.getMonth()].toLowerCase()} de ${date.getFullYear()}`;
}

/** "27 de jul – 2 de ago de 2026" (ou "21 – 27 de jul de 2026" quando cai no mesmo mês). */
export function weekRangeLabel(days: Date[]): string {
  const first = days[0];
  const last = days[days.length - 1];
  const shortMonth = (d: Date) => MONTH_LABELS[d.getMonth()].slice(0, 3).toLowerCase();
  if (first.getMonth() === last.getMonth() && first.getFullYear() === last.getFullYear()) {
    return `${first.getDate()} – ${last.getDate()} de ${shortMonth(first)} de ${first.getFullYear()}`;
  }
  if (first.getFullYear() === last.getFullYear()) {
    return `${first.getDate()} de ${shortMonth(first)} – ${last.getDate()} de ${shortMonth(last)} de ${first.getFullYear()}`;
  }
  return `${first.getDate()} de ${shortMonth(first)} de ${first.getFullYear()} – ${last.getDate()} de ${shortMonth(last)} de ${last.getFullYear()}`;
}

/** "27 de jul – 9 de ago de 2026", usado pela view Agenda (janela rolante de N dias). */
export function rangeLabel(from: Date, to: Date): string {
  return weekRangeLabel([from, to]);
}

/** Rótulo curto de dia de semana + dia, ex. "Qua 29", usado nos cabeçalhos das views Semana/Dia. */
export function shortDayLabel(date: Date): string {
  return `${WEEKDAY_HEADER_LABELS[(date.getDay() + 6) % 7]} ${date.getDate()}`;
}

/** Horas cheias do dia (0..23) — usado para montar as linhas dos grids de Semana/Dia. */
export const DAY_HOURS = Array.from({ length: 24 }, (_, h) => h);

export function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}
