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
